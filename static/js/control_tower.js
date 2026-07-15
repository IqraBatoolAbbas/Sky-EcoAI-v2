document.addEventListener("DOMContentLoaded", () => {
  const ROUTE_COLORS = ["#5b8def", "#34d399", "#f2a65a", "#a78bfa", "#f472b6", "#22d3ee"];
  let fleetMap = null;
  let mapLayers = [];
  let selectedMode = "all";
  let pendingCopilotConfirm = null;

  const fmt = (n, d = 1) => (n == null ? "—" : Number(n).toLocaleString("en-PK", { maximumFractionDigits: d }));
  const api = async (url, opts = {}) => {
    const res = await fetch(url, { headers: { "Content-Type": "application/json", Accept: "application/json" }, ...opts });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  };

  /* ---------- Navigation ---------- */
  document.querySelectorAll(".tower-nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tower-nav-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tower-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`panel-${btn.dataset.panel}`).classList.add("active");
      if (btn.dataset.panel === "map") setTimeout(() => fleetMap?.invalidateSize(), 200);
    });
  });

  /* ---------- Overview ---------- */
  async function refreshOverview() {
    const dash = await api("/api/fleet/dashboard");
    const state = await api("/api/fleet/state");
    const k = dash.kpis;
    document.getElementById("overviewKpis").innerHTML = [
      kpi("Active vehicles", k.active_vehicles, "good"),
      kpi("At-risk orders", k.at_risk_orders, k.at_risk_orders ? "bad" : ""),
      kpi("Pending", k.pending_orders),
      kpi("Distance (km)", fmt(k.total_distance_km), "", true),
      kpi("Cost (PKR)", fmt(k.total_cost_pkr, 0), "", true),
      kpi("Est. CO₂e (kg)", fmt(k.total_co2_kg, 2), k.total_co2_kg > k.carbon_budget_kg ? "warn" : "good"),
      kpi("Carbon budget", `${fmt(k.carbon_budget_used_pct, 0)}%`, k.carbon_budget_used_pct > 100 ? "bad" : ""),
    ].join("");

    const alerts = dash.alerts?.length
      ? dash.alerts.map((a) => `<li class="${a.level}">${a.message}</li>`).join("")
      : '<li class="good">No active alerts — fleet nominal.</li>';
    document.getElementById("alertList").innerHTML = alerts;

    const vehicles = state.vehicles || [];
    document.getElementById("vehicleTable").innerHTML = `
      <table class="data-table">
        <thead><tr><th>ID</th><th>Name</th><th>Engine</th><th>Status</th><th>Range</th></tr></thead>
        <tbody>${vehicles.map((v) => `
          <tr>
            <td>${v.id}</td><td>${v.name}</td><td>${v.engine_type}</td>
            <td><span class="status-pill ${v.status}">${v.status}</span></td>
            <td>${v.fuel_or_range_pct}%</td>
          </tr>`).join("")}
        </tbody>
      </table>`;

    renderMap(state);
    renderAtRisk(state.orders);
    renderDecisions(await api("/api/fleet/decisions"));
    renderImpact(await api("/api/fleet/impact"));
    renderPlans(state.candidate_plans || []);
  }

  function kpi(label, val, cls = "", mono = false) {
    return `<div class="kpi-card ${cls}"><small>${label}</small><span class="val"${mono ? ' style="font-family:var(--font-mono)"' : ""}>${val}</span></div>`;
  }

  /* ---------- Map ---------- */
  function initMap() {
    if (fleetMap) return;
    fleetMap = L.map("fleetMap", { zoomControl: true }).setView([31.5204, 74.3587], 11);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap",
    }).addTo(fleetMap);
  }

  function renderMap(state) {
    initMap();
    mapLayers.forEach((l) => fleetMap.removeLayer(l));
    mapLayers = [];

    const depot = state.depot;
    if (depot) {
      const m = L.marker([depot.lat, depot.lng], { title: "Depot" })
        .bindPopup(`<b>${depot.name}</b>`)
        .addTo(fleetMap);
      mapLayers.push(m);
    }

    (state.orders || []).forEach((o) => {
      const color = o.status === "at_risk" ? "#ef4b5f" : o.priority === "high" ? "#f2a65a" : "#8c93ad";
      const m = L.circleMarker([o.lat, o.lng], { radius: 6, color, fillColor: color, fillOpacity: 0.8 })
        .bindPopup(`<b>${o.customer}</b><br>${o.id} · ${o.weight_kg}kg · ${o.status}`)
        .addTo(fleetMap);
      mapLayers.push(m);
    });

    const plan = state.active_plan;
    const routes = plan?.vehicle_routes || [];
    routes.forEach((route, i) => {
      const coords = route.polyline_coords || [];
      if (coords.length < 2) return;
      const line = L.polyline(coords, { color: ROUTE_COLORS[i % ROUTE_COLORS.length], weight: 4, opacity: 0.85 })
        .bindPopup(`${route.vehicle_name}: ${route.order_count} stops, ${route.distance_km} km`)
        .addTo(fleetMap);
      mapLayers.push(line);
    });

    document.getElementById("mapLegend").textContent = plan
      ? `Active plan: ${plan.label || plan.mode} · ${routes.length} routes · ${plan.deliveries_assigned || 0} deliveries`
      : "No active plan — run optimization to plot routes.";

    if (mapLayers.length) {
      const group = L.featureGroup(mapLayers);
      fleetMap.fitBounds(group.getBounds().pad(0.12));
    }
  }

  /* ---------- Optimization ---------- */
  document.querySelectorAll(".mode-selector .filter-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".mode-selector .filter-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      selectedMode = pill.dataset.mode;
    });
  });

  document.getElementById("optimizeBtn").addEventListener("click", async () => {
    setStatus("Optimizing fleet…");
    const data = await api("/api/fleet/optimize", { method: "POST", body: JSON.stringify({ mode: selectedMode }) });
    renderPlans(data.plans || []);
    await refreshOverview();
    setStatus("Plans generated");
  });

  function renderPlans(plans) {
    const el = document.getElementById("planComparison");
    if (!plans.length) {
      el.innerHTML = "<p style='color:var(--text-muted)'>No plans yet. Click Generate route plans.</p>";
      return;
    }
    el.innerHTML = plans.map((p, i) => `
      <div class="plan-card ${i === 0 ? "recommended" : ""}">
        <h4>${p.label || p.mode} ${i === 0 ? "★ Recommended" : ""}</h4>
        <div class="plan-metric"><span>Score</span><b>${fmt(p.score, 2)}</b></div>
        <div class="plan-metric"><span>Deliveries</span><b>${p.deliveries_assigned || 0}</b></div>
        <div class="plan-metric"><span>Distance</span><b>${fmt(p.total_distance_km)} km</b></div>
        <div class="plan-metric"><span>Cost</span><b>PKR ${fmt(p.total_operating_cost_pkr, 0)}</b></div>
        <div class="plan-metric"><span>Est. CO₂e</span><b>${fmt(p.total_co2_kg, 2)} kg</b></div>
        ${p.unassigned_orders?.length ? `<div class="plan-metric"><span>Unassigned</span><b style="color:var(--danger)">${p.unassigned_orders.length}</b></div>` : ""}
        <button class="primary-btn apply-plan-btn" data-plan-id="${p.id}" style="width:100%;margin-top:10px;font-size:12px;">Apply plan</button>
      </div>`).join("");

    el.querySelectorAll(".apply-plan-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await api(`/api/fleet/plans/${btn.dataset.planId}/apply`, { method: "POST", body: "{}" });
        await refreshOverview();
        setStatus("Plan applied");
      });
    });
  }

  /* ---------- Events ---------- */
  document.querySelectorAll(".event-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const type = btn.dataset.event;
      let body = { type };
      if (type === "breakdown" || type === "range_warning") {
        if (btn.dataset.vehicle) body.vehicle_id = btn.dataset.vehicle;
      }
      if (type === "road_blockage") body = { type, lat: 31.52, lng: 74.34, radius_km: 2.5 };
      if (type === "urgent_order") {
        body = {
          type,
          customer: "Emergency Medical Supply",
          lat: 31.49,
          lng: 74.35,
          weight_kg: 40,
          deadline_minutes: 45,
        };
      }
      setStatus(`Simulating ${type}…`);
      await api("/api/fleet/events", { method: "POST", body: JSON.stringify(body) });
      await refreshOverview();
      setStatus("Disruption simulated");
    });
  });

  document.getElementById("generateRecoveryBtn").addEventListener("click", async () => {
    const auto = document.getElementById("autoRecoveryCheck").checked;
    setStatus("Generating recovery…");
    const data = await api("/api/fleet/recovery", {
      method: "POST",
      body: JSON.stringify({ trigger: "event_center", auto_apply: auto }),
    });
    renderPlans(data.recovery_plans || []);
    await refreshOverview();
    setStatus(auto ? "Recovery auto-applied" : "Recovery plans ready");
  });

  function renderAtRisk(orders) {
    const atRisk = (orders || []).filter((o) => o.status === "at_risk");
    document.getElementById("atRiskList").innerHTML = atRisk.length
      ? `<ul class="alert-list">${atRisk.map((o) => `<li class="critical">${o.id} — ${o.customer}</li>`).join("")}</ul>`
      : "<p style='color:var(--text-muted);font-size:13px'>No at-risk deliveries.</p>";
  }

  function renderDecisions(data) {
    const decisions = data.decisions || [];
    document.getElementById("decisionTimeline").innerHTML = decisions.length
      ? decisions.slice().reverse().map((d) => `
        <div class="timeline-item">
          <time>${new Date(d.timestamp).toLocaleString()}</time>
          <strong>${d.trigger}</strong> — ${d.explanation || ""}
          <div style="color:var(--text-faint);margin-top:4px">${d.approval_status || ""}</div>
        </div>`).join("")
      : "<p style='color:var(--text-muted);font-size:13px'>No agent decisions yet.</p>";
  }

  /* ---------- Copilot ---------- */
  const copilotMessages = document.getElementById("copilotMessages");
  const appendMsg = (text, role, tools = "") => {
    const div = document.createElement("div");
    div.className = `copilot-msg ${role}`;
    div.innerHTML = text + (tools ? `<div class="tools">Tools: ${tools}</div>` : "");
    copilotMessages.appendChild(div);
    copilotMessages.scrollTop = copilotMessages.scrollHeight;
  };

  async function sendCopilot(message, confirm = false) {
    appendMsg(message, "user");
    const data = await api("/api/fleet/copilot", {
      method: "POST",
      body: JSON.stringify({
        message,
        confirm,
        pending_action: confirm ? pendingCopilotConfirm : null,
      }),
    });
    appendMsg(data.reply, "bot", (data.tool_calls || []).map((t) => t.tool).join(", "));
    if (data.pending_confirmation) {
      pendingCopilotConfirm = data.pending_confirmation;
      appendMsg("⚠️ Confirm this action? Send message: <b>yes confirm</b>", "bot");
    } else {
      pendingCopilotConfirm = null;
    }
    await refreshOverview();
  }

  document.getElementById("copilotForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("copilotInput");
    const msg = input.value.trim();
    if (!msg) return;
    input.value = "";
    const confirm = pendingCopilotConfirm && /^(yes|confirm|yes confirm)/i.test(msg);
    await sendCopilot(confirm ? msg : msg, confirm);
  });

  document.querySelectorAll(".copilot-prompt").forEach((btn) => {
    btn.addEventListener("click", () => sendCopilot(btn.textContent.trim()));
  });

  /* ---------- Impact ---------- */
  function renderImpact(summary) {
    document.getElementById("impactKpis").innerHTML = [
      kpi("Km planned", fmt(summary.km_planned), "", true),
      kpi("Est. cost (PKR)", fmt(summary.estimated_cost_pkr, 0), "", true),
      kpi("Est. CO₂e (kg)", fmt(summary.estimated_co2_kg, 2), "good"),
      kpi("CO₂ avoided (kg)", fmt(summary.co2_avoided_vs_baseline_kg, 2), "good"),
      kpi("Deliveries protected", summary.deliveries_protected || 0, "good"),
      kpi("Disruptions resolved", summary.disruptions_resolved || 0),
      kpi("Agent actions", summary.agent_actions || 0),
    ].join("");

    const hist = summary.disruption_history || [];
    document.getElementById("disruptionHistory").innerHTML = hist.length
      ? `<ul class="alert-list">${hist.map((e) => `<li>${e.type} · ${new Date(e.timestamp).toLocaleString()}</li>`).join("")}</ul>`
      : "<p style='color:var(--text-muted);font-size:13px'>No disruptions recorded yet.</p>";
  }

  /* ---------- Reset ---------- */
  document.getElementById("resetDemoBtn").addEventListener("click", async () => {
    if (!confirm("Reset demo to Lahore seed scenario?")) return;
    await api("/api/fleet/reset-demo", { method: "POST", body: "{}" });
    copilotMessages.innerHTML = "";
    await refreshOverview();
    setStatus("Demo reset complete");
  });

  function setStatus(msg) {
    document.getElementById("systemStatus").innerHTML = `<span class="dot ok"></span> ${msg}`;
  }

  refreshOverview().catch((err) => setStatus(`Error: ${err.message}`));
});
