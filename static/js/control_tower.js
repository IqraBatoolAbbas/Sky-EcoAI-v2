document.addEventListener("DOMContentLoaded", () => {
  const ROUTE_COLORS = ["#5b8def", "#34d399", "#f2a65a", "#a78bfa", "#f472b6", "#22d3ee"];
  let fleetMap = null;
  let mapLayers = [];
  let selectedMode = "all";
  let pendingCopilotConfirm = null;

  const fmt = (n, d = 1) => (n == null ? "—" : Number(n).toLocaleString("en-PK", { maximumFractionDigits: d }));
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);
  let demoStep = 1;

  const api = async (url, opts = {}) => {
    const res = await fetch(url, { headers: { "Content-Type": "application/json", Accept: "application/json" }, ...opts });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) {
      window.location.href = "/login?next=/control-tower";
      throw new Error(data.error || "Authentication required");
    }
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  };

  function goPanel(name) {
    document.querySelectorAll(".tower-nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.panel === name));
    document.querySelectorAll(".tower-panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${name}`));
    if (name === "map") setTimeout(() => fleetMap?.invalidateSize(), 200);
  }

  function markDemoStep(step) {
    demoStep = step;
    document.querySelectorAll("#demoSteps li").forEach((li) => {
      const s = Number(li.dataset.step);
      li.classList.toggle("active", s === step);
      li.classList.toggle("done", s < step);
    });
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }


  /* ---------- Navigation ---------- */
  document.querySelectorAll(".tower-nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => goPanel(btn.dataset.panel));
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
      ? dash.alerts.map((a) => `<li class="${escapeHtml(a.level)}">${escapeHtml(a.message)}</li>`).join("")
      : '<li class="good">No active alerts — fleet nominal.</li>';
    document.getElementById("alertList").innerHTML = alerts;

    const activity = dash.activity_log || [];
    const actEl = document.getElementById("activityLog");
    if (actEl) {
      actEl.innerHTML = activity.length
        ? activity.map((a) => `
          <div class="timeline-item">
            <time>${new Date(a.timestamp).toLocaleString()}</time>
            <strong>${escapeHtml(a.actor)}</strong> — ${escapeHtml(a.action)}
            <div style="color:var(--text-faint);margin-top:4px">${escapeHtml(a.detail || "")}</div>
          </div>`).join("")
        : "<p style='color:var(--text-muted);font-size:13px'>No operator actions yet.</p>";
    }

    const vehicles = state.vehicles || [];
    document.getElementById("vehicleTable").innerHTML = `
      <table class="data-table">
        <thead><tr><th>ID</th><th>Name</th><th>Engine</th><th>Status</th><th>Range</th></tr></thead>
        <tbody>${vehicles.map((v) => `
          <tr>
            <td>${escapeHtml(v.id)}</td><td>${escapeHtml(v.name)}</td><td>${escapeHtml(v.engine_type)}</td>
            <td><span class="status-pill ${escapeHtml(v.status)}">${escapeHtml(v.status)}</span></td>
            <td>${v.fuel_or_range_pct}%</td>
          </tr>`).join("")}
        </tbody>
      </table>`;

    renderMap(state);
    renderAtRisk(state.orders);
    const decisionsData = await api("/api/fleet/decisions");
    renderDecisions(decisionsData);
    const overviewTl = document.getElementById("overviewTimeline");
    if (overviewTl) {
      overviewTl.innerHTML = document.getElementById("decisionTimeline").innerHTML;
    }
    renderImpact(await api("/api/fleet/impact"));
    renderPlans(state.candidate_plans || []);
    await loadAlerts();

    // Infer demo step from state
    if (state.active_plan && (state.events || []).some((e) => e.type === "recovery_applied")) markDemoStep(5);
    else if ((state.events || []).some((e) => e.type === "breakdown")) markDemoStep(4);
    else if (state.active_plan) markDemoStep(3);
    else if ((state.candidate_plans || []).length) markDemoStep(2);
    else markDemoStep(1);
  }

  async function loadAlerts() {
    try {
      const data = await api("/api/fleet/alerts");
      const alerts = data.alerts || [];
      const ticker = document.getElementById("alertsTicker");
      if (!ticker) return;
      if (!alerts.length) {
        ticker.hidden = true;
        return;
      }
      const latest = alerts[0];
      ticker.hidden = false;
      ticker.innerHTML = `<strong>${escapeHtml(latest.title || "Alert")}</strong> · ${escapeHtml(latest.body || "")} <span style="color:var(--text-faint)">(${escapeHtml((latest.channels || []).join(", "))} · simulated)</span>`;
    } catch (_) { /* ignore */ }
  }

  async function loadNarrative() {
    const data = await api("/api/fleet/impact/narrative");
    const text = document.getElementById("impactNarrativeText");
    if (text) text.textContent = data.narrative || "";
    const pitch = document.getElementById("judgePitch");
    const narr = document.getElementById("judgeNarrative");
    const board = document.getElementById("impactScoreboard");
    const sdg = document.getElementById("sdgRow");
    if (narr) narr.textContent = data.narrative || "";
    if (board) {
      const eq = data.equivalents || {};
      const s = data.summary || {};
      board.innerHTML = [
        ["Impact score", s.impact_score ?? "—"],
        ["CO₂ avoided vs petrol (kg)", eq.co2_avoided_kg ?? 0],
        ["Fuel eq. (L)", eq.fuel_liters_avoided_est ?? 0],
        ["Trees eq.", eq.trees_annual_uptake_est ?? 0],
        ["Deliveries", s.deliveries_protected ?? 0],
      ].map(([l, v]) => `<div>${l}<strong>${v}</strong></div>`).join("");
    }
    if (sdg && data.sdg) {
      sdg.textContent = `${data.sdg.primary} · ${(data.sdg.secondary || []).join(" · ")}`;
    }
    if (pitch) pitch.hidden = false;
    return data;
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
        .bindPopup(`<b>${escapeHtml(depot.name)}</b>`)
        .addTo(fleetMap);
      mapLayers.push(m);
    }

    (state.orders || []).forEach((o) => {
      const color = o.status === "at_risk" ? "#ef4b5f" : o.priority === "high" ? "#f2a65a" : "#8c93ad";
      const m = L.circleMarker([o.lat, o.lng], { radius: 6, color, fillColor: color, fillOpacity: 0.8 })
        .bindPopup(`<b>${escapeHtml(o.customer)}</b><br>${escapeHtml(o.id)} · ${fmt(o.weight_kg, 0)}kg · ${escapeHtml(o.status)}`)
        .addTo(fleetMap);
      mapLayers.push(m);
    });

    const plan = state.active_plan;
    const routes = plan?.vehicle_routes || [];
    routes.forEach((route, i) => {
      const coords = route.polyline_coords || [];
      if (coords.length < 2) return;
      const line = L.polyline(coords, { color: ROUTE_COLORS[i % ROUTE_COLORS.length], weight: 4, opacity: 0.85 })
        .bindPopup(`${escapeHtml(route.vehicle_name)}: ${fmt(route.order_count, 0)} stops, ${fmt(route.distance_km)} km`)
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
    const enforce = document.getElementById("carbonEnforceCheck")?.checked ?? true;
    try {
      await api("/api/fleet/carbon-enforcement", { method: "POST", body: JSON.stringify({ enabled: enforce }) });
    } catch (_) { /* non-fatal */ }
    const prog = document.getElementById("optProgress");
    const bar = document.getElementById("optProgressBar");
    prog?.classList.add("visible");
    if (bar) bar.style.width = "35%";
    const data = await api("/api/fleet/optimize", { method: "POST", body: JSON.stringify({ mode: selectedMode }) });
    if (bar) bar.style.width = "100%";
    renderPlans(data.plans || []);
    markDemoStep(2);
    await refreshOverview();
    setTimeout(() => prog?.classList.remove("visible"), 600);
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
        <h4>${escapeHtml(p.label || p.mode)} ${i === 0 ? "★ Recommended" : ""}</h4>
        <div class="plan-metric"><span>Score</span><b>${fmt(p.score, 2)}</b></div>
        <div class="plan-metric"><span>Deliveries</span><b>${p.deliveries_assigned || 0}</b></div>
        <div class="plan-metric"><span>Distance</span><b>${fmt(p.total_distance_km)} km</b></div>
        <div class="plan-metric"><span>Cost</span><b>PKR ${fmt(p.total_operating_cost_pkr, 0)}</b></div>
        <div class="plan-metric"><span>Est. CO₂e</span><b>${fmt(p.total_co2_kg, 2)} kg</b></div>
        ${p.unassigned_orders?.length ? `<div class="plan-metric"><span>Unassigned</span><b style="color:var(--danger)">${p.unassigned_orders.length}</b></div>` : ""}
        <span class="budget-badge ${p.within_carbon_budget === false ? "bad" : "ok"}">
          ${p.within_carbon_budget === false ? "Over carbon budget" : "Within carbon budget"}
        </span>
        <button class="primary-btn apply-plan-btn" data-plan-id="${escapeHtml(p.id)}" style="width:100%;margin-top:10px;font-size:12px;">Apply plan</button>
      </div>`).join("");

    el.querySelectorAll(".apply-plan-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await api(`/api/fleet/plans/${btn.dataset.planId}/apply`, { method: "POST", body: "{}" });
        markDemoStep(3);
        await refreshOverview();
        goPanel("map");
        setStatus("Plan applied");
      });
    });
  }

  /* ---------- Events ---------- */
  document.querySelectorAll(".scenario-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const scenario = btn.dataset.scenario;
      setStatus(`Running scenario: ${scenario}…`);
      const data = await api("/api/fleet/scenarios", {
        method: "POST",
        body: JSON.stringify({ scenario }),
      });
      await refreshOverview();
      goPanel("events");
      setStatus(`Scenario ready: ${data.title || scenario}`);
    });
  });

  document.getElementById("nlScenarioForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("nlScenarioInput");
    const status = document.getElementById("nlScenarioStatus");
    const prompt = input.value.trim();
    if (!prompt) return;
    status.textContent = "Parsing with GenAI intent layer…";
    setStatus("NL scenario…");
    const data = await api("/api/fleet/scenario/nl", {
      method: "POST",
      body: JSON.stringify({ prompt, auto_recover: true }),
    });
    status.textContent = `${data.parsed?.summary || "Done"} · generator: ${data.parsed?.generator || "n/a"}`;
    if (data.recovery?.recovery_plans) renderPlans(data.recovery.recovery_plans);
    markDemoStep(4);
    await refreshOverview();
    setStatus("NL scenario staged — review recovery plans");
  });

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
      if (type === "breakdown") markDemoStep(4);
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
    markDemoStep(auto ? 5 : 4);
    await refreshOverview();
    if (auto) goPanel("impact");
    setStatus(auto ? "Recovery auto-applied" : "Recovery plans ready");
  });

  function renderAtRisk(orders) {
    const atRisk = (orders || []).filter((o) => o.status === "at_risk");
    document.getElementById("atRiskList").innerHTML = atRisk.length
      ? `<ul class="alert-list">${atRisk.map((o) => `<li class="critical">${escapeHtml(o.id)} — ${escapeHtml(o.customer)}</li>`).join("")}</ul>`
      : "<p style='color:var(--text-muted);font-size:13px'>No at-risk deliveries.</p>";
  }

  function renderDecisions(data) {
    const decisions = data.decisions || [];
    document.getElementById("decisionTimeline").innerHTML = decisions.length
      ? decisions.slice().reverse().map((d) => `
        <div class="timeline-item">
          <time>${new Date(d.timestamp).toLocaleString()}</time>
          <strong>${escapeHtml(d.trigger)}</strong> — ${escapeHtml(d.explanation || "")}
          <div style="color:var(--text-faint);margin-top:4px">${escapeHtml(d.approval_status || "")}</div>
        </div>`).join("")
      : "<p style='color:var(--text-muted);font-size:13px'>No agent decisions yet.</p>";
  }

  /* ---------- Copilot ---------- */
  const copilotMessages = document.getElementById("copilotMessages");
  const appendMsg = (text, role, tools = "") => {
    const div = document.createElement("div");
    div.className = `copilot-msg ${role}`;
    div.textContent = text;
    if (tools) {
      const toolInfo = document.createElement("div");
      toolInfo.className = "tools";
      toolInfo.textContent = `Tools: ${tools}`;
      div.appendChild(toolInfo);
    }
    copilotMessages.appendChild(div);
    copilotMessages.scrollTop = copilotMessages.scrollHeight;
  };

  async function sendCopilot(message, confirm = false) {
    const lower = message.trim().toLowerCase();
    // Voice / prompt shortcuts that drive the tower UI
    if (/guided demo|run demo|start demo/.test(lower)) {
      appendMsg(message, "user");
      appendMsg("Starting guided demo…", "bot");
      document.getElementById("runDemoBtn")?.click();
      return;
    }
    if (/reset demo|reset scenario/.test(lower)) {
      appendMsg(message, "user");
      await api("/api/fleet/reset-demo", { method: "POST", body: "{}" });
      markDemoStep(1);
      await refreshOverview();
      appendMsg("Demo reset to Lahore seed.", "bot");
      return;
    }
    if (/^optimize\b|generate (fleet )?plans|optimize fleet/.test(lower)) {
      appendMsg(message, "user");
      goPanel("optimize");
      document.getElementById("optimizeBtn")?.click();
      appendMsg("Optimization Studio is generating Economy / Green / Service plans.", "bot");
      return;
    }

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
      appendMsg("⚠️ Confirm this action? Send message: yes confirm", "bot");
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

  // Free browser voice (Web Speech API) — Whisper optional later
  if (window.SkyVoice) {
    SkyVoice.attachMicButton(
      document.getElementById("copilotMicBtn"),
      document.getElementById("copilotInput"),
      { onSubmit: (t) => sendCopilot(t) }
    );
  }

  /* ---------- Impact ---------- */
  function renderImpact(summary) {
    document.getElementById("impactKpis").innerHTML = [
      kpi("Impact score", summary.impact_score ?? "—", "good"),
      kpi("Km planned", fmt(summary.km_planned), "", true),
      kpi("Est. cost (PKR)", fmt(summary.estimated_cost_pkr, 0), "", true),
      kpi("Est. CO₂e (kg)", fmt(summary.estimated_co2_kg, 2), "good"),
      kpi("CO₂ avoided vs petrol (kg)", fmt(summary.co2_avoided_vs_conventional_kg, 2), "good"),
      kpi("Deliveries protected", summary.deliveries_protected || 0, "good"),
      kpi("Disruptions resolved", summary.disruptions_resolved || 0),
      kpi("Agent actions", summary.agent_actions || 0),
    ].join("");

    renderDelta(summary.delta);

    const hist = summary.disruption_history || [];
    document.getElementById("disruptionHistory").innerHTML = hist.length
      ? `<ul class="alert-list">${hist.map((e) => `<li>${escapeHtml(e.type)} · ${new Date(e.timestamp).toLocaleString()}</li>`).join("")}</ul>`
      : "<p style='color:var(--text-muted);font-size:13px'>No disruptions recorded yet.</p>";
  }

  function renderDelta(delta) {
    const strip = document.getElementById("deltaStrip");
    const grid = document.getElementById("deltaGrid");
    if (!strip || !grid) return;
    if (!delta || !delta.before) {
      strip.hidden = true;
      return;
    }
    strip.hidden = false;
    const rows = [
      ["Distance (km)", delta.distance_km, delta.before.distance_km, delta.after.distance_km, true],
      ["Cost (PKR)", delta.cost_pkr, delta.before.cost_pkr, delta.after.cost_pkr, true],
      ["Est. CO₂e (kg)", delta.co2_kg, delta.before.co2_kg, delta.after.co2_kg, true],
      ["Deliveries", delta.deliveries, delta.before.deliveries, delta.after.deliveries, false],
    ];
    grid.innerHTML = rows.map(([label, d, b, a, lowerBetter]) => {
      const better = lowerBetter ? d <= 0 : d >= 0;
      const sign = d > 0 ? "+" : "";
      return `<div class="delta-card">
        <small>${label}</small>
        <div class="delta-val ${better ? "better" : "worse"}">${sign}${fmt(d, 2)}</div>
        <div class="delta-detail">${fmt(b, 2)} → ${fmt(a, 2)}</div>
      </div>`;
    }).join("");
  }

  /* ---------- Reset + guided demo ---------- */
  document.getElementById("resetDemoBtn").addEventListener("click", async () => {
    if (!confirm("Reset demo to Lahore seed scenario?")) return;
    await api("/api/fleet/reset-demo", { method: "POST", body: "{}" });
    copilotMessages.innerHTML = "";
    markDemoStep(1);
    await refreshOverview();
    setStatus("Demo reset complete");
  });

  document.getElementById("runDemoBtn")?.addEventListener("click", async () => {
    const btn = document.getElementById("runDemoBtn");
    btn.disabled = true;
    try {
      setStatus("Guided demo running…");
      await api("/api/fleet/reset-demo", { method: "POST", body: "{}" });
      markDemoStep(1);
      goPanel("optimize");
      await sleep(400);
      const opt = await api("/api/fleet/optimize", { method: "POST", body: JSON.stringify({ mode: "all" }) });
      renderPlans(opt.plans || []);
      markDemoStep(2);
      await sleep(500);
      const pid = opt.recommended_plan_id || opt.plans?.[0]?.id;
      await api(`/api/fleet/plans/${pid}/apply`, { method: "POST", body: "{}" });
      markDemoStep(3);
      goPanel("map");
      await sleep(700);
      goPanel("events");
      await api("/api/fleet/events", { method: "POST", body: JSON.stringify({ type: "breakdown" }) });
      markDemoStep(4);
      await sleep(500);
      const rec = await api("/api/fleet/recovery", {
        method: "POST",
        body: JSON.stringify({ trigger: "guided_demo", auto_apply: true }),
      });
      renderPlans(rec.recovery_plans || []);
      markDemoStep(5);
      goPanel("impact");
      await refreshOverview();
      await loadNarrative();
      setStatus("Guided demo complete — ask Copilot why the plan was selected");
    } catch (err) {
      setStatus(`Demo error: ${err.message}`);
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("judgeModeBtn")?.addEventListener("click", async () => {
    goPanel("overview");
    setStatus("Judge Mode: generating GenAI impact pitch…");
    try {
      await loadNarrative();
      document.getElementById("judgePitch")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      setStatus("Judge Mode ready — narrative + SDG scoreboard");
    } catch (err) {
      setStatus(`Judge Mode error: ${err.message}`);
    }
  });

  document.getElementById("regenNarrativeBtn")?.addEventListener("click", async () => {
    setStatus("Regenerating narrative…");
    await loadNarrative();
    setStatus("Narrative refreshed");
  });

  function setStatus(msg) {
    const status = document.getElementById("systemStatus");
    status.textContent = "";
    const dot = document.createElement("span");
    dot.className = "dot ok";
    status.append(dot, document.createTextNode(` ${msg}`));
  }

  refreshOverview().catch((err) => setStatus(`Error: ${err.message}`));
});
