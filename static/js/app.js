// static/js/app.js
document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("workspaceRoot");
  const form = document.querySelector("#routeForm");
  const statusLine = document.querySelector("#statusLine");
  const statusText = document.querySelector("#statusText");
  const submitBtn = document.querySelector("#routeSubmit");
  const fleetGrid = document.querySelector("#fleetGrid");
  const mapCaption = document.getElementById("mapCaption");

  const defaultVehicle = root.dataset.defaultVehicle || "petrol";
  const units = root.dataset.defaultUnits || "km";
  const KM_TO_MI = 0.621371;

  const formatNum = (number) => new Intl.NumberFormat("en-PK").format(Math.round(number));
  const formatDistance = (km) => units === "mi" ? `${formatNum(km * KM_TO_MI)} mi` : `${formatNum(km)} km`;

  let lastResult = null;
  const currentUserId = document.body.getAttribute("data-user-id") || "guest";
  const isUserLoggedIn = document.body.getAttribute("data-logged-in") === "true";
  
  /* ---------------- FLEET PICKER ---------------- */
  const defaultOpt = fleetGrid.querySelector(`.fleet-option[data-value="${defaultVehicle}"]`);
  if (defaultOpt) selectFleetOption(defaultOpt);
  fleetGrid.querySelectorAll(".fleet-option").forEach((opt) => opt.addEventListener("click", () => selectFleetOption(opt)));
  function selectFleetOption(opt) {
    fleetGrid.querySelectorAll(".fleet-option").forEach((o) => o.classList.remove("checked"));
    opt.classList.add("checked");
    opt.querySelector("input").checked = true;
  }

  /* ---------------- SWAP SOURCE/DESTINATION ---------------- */
  document.getElementById("swapBtn").addEventListener("click", () => {
    const src = document.getElementById("sourceInput");
    const dst = document.getElementById("destInput");
    [src.value, dst.value] = [dst.value, src.value];
  });

  function setStatus(state, message) {
    statusLine.className = `status-line ${state}`;
    statusText.textContent = message;
  }

  /* ---------------- LEAFLET MAP ---------------- */
  let map = null;
  let routeLine = null;
  let markers = [];

  function initMap() {
    if (map) return;
    map = L.map("routeMap", { zoomControl: true, attributionControl: true }).setView([30.3753, 69.3451], 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
  }

  function clearMap() {
    markers.forEach((m) => map.removeLayer(m));
    markers = [];
    if (routeLine) { map.removeLayer(routeLine); routeLine = null; }
  }

  async function geocode(place) {
    const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=${encodeURIComponent(place)}`;
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error("Geocoding service unavailable.");
    const data = await res.json();
    if (!data.length) throw new Error(`Couldn't find "${place}" on the map.`);
    return { lat: parseFloat(data[0].lat), lon: parseFloat(data[0].lon), label: data[0].display_name };
  }

  async function fetchDrivingRoute(a, b) {
    const url = `https://router.project-osrm.org/route/v1/driving/${a.lon},${a.lat};${b.lon},${b.lat}?overview=full&geometries=geojson`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Routing service unavailable.");
    const data = await res.json();
    if (!data.routes || !data.routes.length) throw new Error("No drivable route found between these points.");
    return data.routes[0];
  }

  async function plotRoute(sourceName, destName) {
    initMap();
    clearMap();
    mapCaption.textContent = "🌐 Locating cities…";

    const [a, b] = await Promise.all([geocode(sourceName), geocode(destName)]);

    mapCaption.textContent = "🌐 Drawing route…";
    const osrmRoute = await fetchDrivingRoute(a, b);
    const latlngs = osrmRoute.geometry.coordinates.map(([lon, lat]) => [lat, lon]);

    routeLine = L.polyline(latlngs, { color: getComputedStyle(document.documentElement).getPropertyValue("--altitude").trim() || "#5b8def", weight: 4, opacity: 0.85 }).addTo(map);

    const srcMarker = L.marker([a.lat, a.lon]).addTo(map).bindPopup(`Source: ${sourceName}`);
    const dstMarker = L.marker([b.lat, b.lon]).addTo(map).bindPopup(`Destination: ${destName}`);
    markers.push(srcMarker, dstMarker);

    map.fitBounds(routeLine.getBounds(), { padding: [28, 28] });
    mapCaption.textContent = `🌐 ${sourceName} → ${destName} · ${(osrmRoute.distance / 1000).toFixed(1)} km live road route`;
  }

  // Init triggers
  renderTripHistory();
  updateWorkspaceMetricsGauges();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const source = form.elements["source"].value.trim();
    const destination = form.elements["destination"].value.trim();

    setStatus("loading", "AI concierge is optimizing the route…");
    submitBtn.disabled = true;
    submitBtn.textContent = "Computing…";
    document.getElementById("savingsBanner").style.display = "none";
    document.getElementById("resultActions").style.display = "none";

    const mapPromise = plotRoute(source, destination).catch((mapErr) => {
      mapCaption.textContent = `⚠ ${mapErr.message}`;
    });

    try {
      const response = await fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source, destination, vehicle: form.elements["vehicle"].value })
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Something went wrong during the optimization pipeline.");

      document.querySelector("#tripTitle").textContent = `${data.source} → ${data.destination}`;
      document.querySelector("#recommendation").textContent = data.recommendation;

      document.querySelector("#sprintDistance").textContent = formatDistance(data.routes.sprint.distance);
      document.querySelector("#sprintDuration").textContent = `${data.routes.sprint.duration} min`;
      document.querySelector("#sprintCo2").textContent = `${formatNum(data.routes.sprint.co2)} g`;

      document.querySelector("#greenDistance").textContent = formatDistance(data.routes.green.distance);
      document.querySelector("#greenDuration").textContent = `${data.routes.green.duration} min`;
      document.querySelector("#greenCo2").textContent = `${formatNum(data.routes.green.co2)} g`;

      document.querySelector("#savedCo2").textContent = `${formatNum(data.savings.co2)} g (${data.savings.percent}%)`;
      document.getElementById("savingsBanner").style.display = "flex";
      document.getElementById("resultActions").style.display = "flex";

      lastResult = data;

      // ===================================================================================
      // UPDATED TELEMETRY WRITER: Synchronizes perfectly with dashboard.js & index.html
      // ===================================================================================
      // ===================================================================================
      // UPDATED TELEMETRY WRITER: Synchronizes with server-side API & LocalStorage
      // ===================================================================================
      const tripData = {
        id: Date.now(),
        userId: currentUserId,
        query: `${data.source} ➔ ${data.destination}`,
        engine: (data.vehicle || form.elements["vehicle"].value).toLowerCase(),
        sprintCo2: data.routes.sprint.co2,
        greenCo2: data.routes.green.co2,
        saved: data.savings.co2,
        savings: { co2: data.savings.co2 },
        favorite: false
      };

      // 1. Send to Backend API for Server-side persistence (Forecasting Agent sync)
      try {
        await fetch("/api/ledger", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(tripData)
        });
      } catch (err) {
        console.warn("Server sync skipped, using local-only mode:", err);
      }

      // 2. Save to LocalStorage for immediate UI performance
      const ledger = JSON.parse(localStorage.getItem("sky_eco_ledger") || "[]");
      ledger.push(tripData);
      localStorage.setItem("sky_eco_ledger", JSON.stringify(ledger));
      
      // Update history list and metrics bar right away
      renderTripHistory();
      updateWorkspaceMetricsGauges();

      setStatus("success", "Route matrix updated and saved to your ledger.");
      SkyToast.show("Route computed and logged.", "success");
    } catch (error) {
      setStatus("error", error.message);
      SkyToast.show(error.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Compute dynamic solution matrix ⚡";
      await mapPromise;
    }
  });
  /* ---------------- FIXED FAVORITE ACTION + AUTH GATEWAY GUARD ---------------- */
  document.getElementById("favoriteBtn").addEventListener("click", (e) => {
    if (!lastResult) return;

    if (!isUserLoggedIn) {
      if (typeof SkyToast !== "undefined") {
        SkyToast.show("Please Log In or Sign Up to save your favorite routes!", "error");
      } else {
        alert("Please Log In or Sign Up to save your favorite routes!");
      }
      window.location.href = "/login";
      return;
    }

    const ledger = JSON.parse(localStorage.getItem("sky_eco_ledger") || "[]");
    const last = ledger[ledger.length - 1];
    if (last) {
      last.favorite = !last.favorite;
      localStorage.setItem("sky_eco_ledger", JSON.stringify(ledger));
      e.target.textContent = last.favorite ? "★ Saved to favorites" : "☆ Save as favorite";
      SkyToast.show(last.favorite ? "Route starred in your ledger." : "Removed from favorites.", "success");
      renderTripHistory();
    }
  });

  /* ---------------- COPY SUMMARY TO CLIPBOARD ---------------- */
  document.getElementById("copySummaryBtn").addEventListener("click", async () => {
    if (!lastResult) return;
    const d = lastResult;
    const summary = `${d.source} → ${d.destination} (${d.vehicle})\nSprint: ${formatDistance(d.routes.sprint.distance)}, ${d.routes.sprint.duration} min, ${formatNum(d.routes.sprint.co2)}g CO2\nGreen: ${formatDistance(d.routes.green.distance)}, ${d.routes.green.duration} min, ${formatNum(d.routes.green.co2)}g CO2\nSaved: ${formatNum(d.savings.co2)}g (${d.savings.percent}%)`;
    try {
      await navigator.clipboard.writeText(summary);
      SkyToast.show("Route summary copied to clipboard.", "success");
    } catch {
      await SkyToast.show("Couldn't copy — your browser may be blocking clipboard access.", "error");
    }
  });

  /* ---------------- RENDER LOCAL TRIP HISTORY ---------------- */
  function renderTripHistory() {
    const list = document.getElementById("tripHistoryList");
    if (!list) return;
    
    const ledger = JSON.parse(localStorage.getItem("sky_eco_ledger") || "[]")
                           .filter(item => (item.userId || "guest") === currentUserId)
                           .slice(-5)
                           .reverse();

    if (ledger.length === 0) {
      list.innerHTML = `<p style="color:var(--text-faint); font-size:13px; margin:10px 0 0;">No trips logged yet this session.</p>`;
      return;
    }
    list.innerHTML = ledger.map((item) => `
      <div class="trip-history-item">
        <span>${item.favorite ? "★ " : ""}${item.query}</span>
        <span class="muted">+${formatNum(item.saved)}g saved</span>
      </div>
    `).join("");
  }

  /* ---------------- RENDER PROGRESS METRICS ---------------- */
  function updateWorkspaceMetricsGauges() {
    try {
      const ledger = JSON.parse(localStorage.getItem("sky_eco_ledger") || "[]")
                           .filter(item => (item.userId || "guest") === currentUserId);

      let totalSaved = 0;
      ledger.forEach(trip => {
        if (trip.saved) totalSaved += parseFloat(trip.saved);
      });

      const totalSavedEl = document.getElementById("totalSavedCo2");
      const totalQueriesEl = document.getElementById("totalQueriesCount");
      const goalFill = document.getElementById("carbonGoalFill");
      const goalText = document.getElementById("carbonGoalText");

      if (totalSavedEl) totalSavedEl.textContent = `${formatNum(totalSaved)} g`;
      if (totalQueriesEl) totalQueriesEl.textContent = ledger.length;

      const targetMetric = 5000;
      let percentage = Math.min(Math.round((totalSaved / targetMetric) * 100), 100);
      if (isNaN(percentage) || percentage < 0) percentage = 0;

      if (goalFill && goalText) {
        goalFill.style.width = percentage + "%";
        goalText.textContent = `${percentage}% completed (${formatNum(totalSaved)}g / ${formatNum(targetMetric)}g)`;
      }
    } catch (err) {
      console.error("Workspace dynamic gauge pipeline trace exception:", err);
    }
  }
});