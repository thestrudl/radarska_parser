// Map + chart wiring for the radar precipitation GUI.
"use strict";

const SI_CENTER = [46.15, 14.99];
const map = L.map("map").setView(SI_CENTER, 8);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

let marker = null;
let chart = null;

// Radar overlay state.
let radarOverlay = null;
let radarBounds = null;
let latestOverlayUrl = null;
let hoverTimer = null;

const statusEl = document.getElementById("status");
const titleEl = document.getElementById("chart-title");
const rangeEl = document.getElementById("range");
const frameTimeEl = document.getElementById("frame-time");
const radarToggle = document.getElementById("radar-toggle");
const radarOpacity = document.getElementById("radar-opacity");

function setStatus(msg) {
  statusEl.textContent = msg || "";
}

function fmtTime(iso) {
  try {
    return luxon.DateTime.fromISO(iso).toFormat("dd LLL HH:mm");
  } catch (_) {
    return iso;
  }
}

// --- Radar overlay -----------------------------------------------------------
async function initRadarOverlay() {
  try {
    const resp = await fetch("/radar/meta");
    if (!resp.ok) {
      frameTimeEl.textContent = "(no radar yet)";
      return;
    }
    const meta = await resp.json();
    radarBounds = meta.bounds;
    latestOverlayUrl = `/radar/overlay.png?t=${encodeURIComponent(meta.time)}`;
    if (radarOverlay) {
      // Already created — just point it at the new latest frame.
      radarOverlay.setBounds(radarBounds);
      radarOverlay.setUrl(latestOverlayUrl);
    } else {
      radarOverlay = L.imageOverlay(latestOverlayUrl, radarBounds, {
        opacity: parseFloat(radarOpacity.value),
        interactive: false,
      });
      if (radarToggle.checked) radarOverlay.addTo(map);
    }
    frameTimeEl.textContent = `radar: ${fmtTime(meta.time)}`;
  } catch (err) {
    frameTimeEl.textContent = "";
  }
}

function showOverlayAt(iso) {
  if (!radarOverlay) return;
  radarOverlay.setUrl(`/radar/overlay.png?time=${encodeURIComponent(iso)}`);
  frameTimeEl.textContent = `radar: ${fmtTime(iso)}`;
}

function restoreLatestOverlay() {
  if (!radarOverlay || !latestOverlayUrl) return;
  radarOverlay.setUrl(latestOverlayUrl);
  fetch("/radar/meta")
    .then((r) => (r.ok ? r.json() : null))
    .then((m) => {
      if (m) frameTimeEl.textContent = `radar: ${fmtTime(m.time)}`;
    })
    .catch(() => {});
}

radarToggle.addEventListener("change", () => {
  if (!radarOverlay) return;
  if (radarToggle.checked) radarOverlay.addTo(map);
  else radarOverlay.remove();
});
radarOpacity.addEventListener("input", () => {
  if (radarOverlay) radarOverlay.setOpacity(parseFloat(radarOpacity.value));
});

function isoHoursAgo(hours) {
  return new Date(Date.now() - hours * 3600 * 1000).toISOString();
}

function renderChart(points, label) {
  const data = points.map((p) => ({ x: p.time, y: p.mm_h }));
  titleEl.textContent = label;

  if (chart) chart.destroy();
  const ctx = document.getElementById("chart").getContext("2d");
  chart = new Chart(ctx, {
    type: "line",
    data: {
      datasets: [
        {
          label: "Precipitation (mm/h)",
          data,
          borderColor: "#1b6fb3",
          backgroundColor: "rgba(27,111,179,0.15)",
          fill: true,
          stepped: true,
          pointRadius: 2,
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { type: "time", time: { tooltipFormat: "DD T" }, title: { display: true, text: "Time" } },
        y: { beginAtZero: true, title: { display: true, text: "mm/h" } },
      },
      plugins: { legend: { display: false } },
      // Hovering a point swaps the map overlay to the radar frame at that moment.
      onHover: (event, elements) => {
        if (!elements.length) return;
        const point = chart.data.datasets[0].data[elements[0].index];
        if (!point) return;
        clearTimeout(hoverTimer);
        hoverTimer = setTimeout(() => showOverlayAt(point.x), 120);
      },
    },
  });

  // Leaving the chart restores the latest radar frame.
  const canvas = document.getElementById("chart");
  canvas.onmouseleave = () => {
    clearTimeout(hoverTimer);
    restoreLatestOverlay();
  };
}

async function loadPoint(lat, lon) {
  const hours = rangeEl.value;
  const from = isoHoursAgo(hours);
  setStatus("Loading…");
  if (marker) marker.remove();
  marker = L.marker([lat, lon]).addTo(map);

  try {
    const url = `/precip/history?lat=${lat.toFixed(4)}&lon=${lon.toFixed(4)}&from=${encodeURIComponent(from)}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    const label = `Precipitation @ ${lat.toFixed(3)}, ${lon.toFixed(3)} (cell ${data.cell_x},${data.cell_y})`;
    renderChart(data.points, label);
    setStatus(data.points.length ? `${data.points.length} points` : "No data yet for this point/range");
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
}

async function searchAddress() {
  const address = document.getElementById("address").value.trim();
  if (!address) return;
  const hours = rangeEl.value;
  const from = isoHoursAgo(hours);
  setStatus("Geocoding…");
  try {
    const url = `/precip/by-address?address=${encodeURIComponent(address)}&from=${encodeURIComponent(from)}`;
    const resp = await fetch(url);
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${resp.status}`);
    }
    const data = await resp.json();
    map.setView([data.lat, data.lon], 10);
    if (marker) marker.remove();
    marker = L.marker([data.lat, data.lon]).addTo(map);
    renderChart(data.points, `Precipitation @ ${address}`);
    setStatus(data.points.length ? `${data.points.length} points` : "No data yet for this point/range");
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
}

map.on("click", (e) => loadPoint(e.latlng.lat, e.latlng.lng));
document.getElementById("search-btn").addEventListener("click", searchAddress);
document.getElementById("address").addEventListener("keydown", (e) => {
  if (e.key === "Enter") searchAddress();
});
rangeEl.addEventListener("change", () => {
  if (marker) {
    const { lat, lng } = marker.getLatLng();
    loadPoint(lat, lng);
  }
});

initRadarOverlay();
setInterval(initRadarOverlay, 5 * 60 * 1000);

// Ask for geolocation and auto-pin if granted.
if ("geolocation" in navigator) {
  setStatus("Requesting your location…");
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      map.setView([pos.coords.latitude, pos.coords.longitude], 10);
      loadPoint(pos.coords.latitude, pos.coords.longitude);
    },
    () => {
      // Denied or unavailable — just show the default view.
      setStatus("Ready — click the map.");
    },
    { timeout: 8000 }
  );
} else {
  setStatus("Ready — click the map.");
}
