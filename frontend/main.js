const API_BASE = window.API_BASE || "http://localhost:8000";

const map = L.map("map", {
  zoomControl: true,
});
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap contributors",
}).addTo(map);
map.setView([0, 0], 2);

let races = [];
let boats = [];
let selectedRaceId = null;
let selectedBoats = new Set();
const boatLayers = new Map();

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(detail.detail || response.statusText);
  }
  return response.json();
}

function formatDateTimeLocal(value) {
  if (!value) return "";
  const date = new Date(value);
  const pad = (n) => String(n).padStart(2, "0");
  const yyyy = date.getFullYear();
  const mm = pad(date.getMonth() + 1);
  const dd = pad(date.getDate());
  const hh = pad(date.getHours());
  const min = pad(date.getMinutes());
  return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
}

async function loadRaces() {
  races = await fetchJSON(`${API_BASE}/race`);
  const raceList = document.getElementById("race-list");
  raceList.innerHTML = "";
  const select = document.getElementById("upload-race");
  select.innerHTML = "";

  races.forEach((race) => {
    const div = document.createElement("div");
    div.className = "race-item";
    div.innerHTML = `<button data-id="${race.id}">${race.name}</button>`;
    raceList.appendChild(div);

    const option = document.createElement("option");
    option.value = race.id;
    option.textContent = race.name;
    select.appendChild(option);
  });

  raceList.onclick = (event) => {
    if (event.target instanceof HTMLButtonElement) {
      select.value = event.target.dataset.id;
      setSelectedRace(parseInt(event.target.dataset.id, 10));
    }
  };

  if (races.length && !selectedRaceId) {
    const first = races[0];
    select.value = first.id;
    setSelectedRace(first.id);
  }
}

function setSelectedRace(raceId) {
  selectedRaceId = raceId;
  selectedBoats.clear();
  document.querySelectorAll("#boat-list input[type=checkbox]").forEach((input) => {
    input.checked = false;
  });
  const race = races.find((item) => item.id === raceId);
  if (race) {
    const startInput = document.getElementById("window-start");
    const endInput = document.getElementById("window-end");
    const startTime = new Date(race.start_time);
    startInput.value = formatDateTimeLocal(startTime.toISOString());
    endInput.value = formatDateTimeLocal(new Date(startTime.getTime() + 5 * 60 * 1000).toISOString());
  }
  loadBoats();
}

async function loadBoats() {
  if (!selectedRaceId) return;
  boats = await fetchJSON(`${API_BASE}/boats?raceId=${selectedRaceId}`);
  renderBoatList();
}

function renderBoatList() {
  const container = document.getElementById("boat-list");
  container.innerHTML = "";
  boats.forEach((boat) => {
    const div = document.createElement("div");
    div.className = "boat-item";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = boat.id;
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        selectedBoats.add(boat.id);
      } else {
        selectedBoats.delete(boat.id);
        const layer = boatLayers.get(boat.id);
        if (layer) {
          map.removeLayer(layer);
          boatLayers.delete(boat.id);
        }
      }
      refreshTracks();
      refreshStats();
    });
    const swatch = document.createElement("span");
    swatch.className = "boat-swatch";
    swatch.style.background = boat.label_color;
    const label = document.createElement("label");
    label.appendChild(checkbox);
    label.appendChild(swatch);
    label.appendChild(document.createTextNode(boat.sail_no));
    div.appendChild(label);
    container.appendChild(div);
  });
}

async function refreshTracks() {
  if (!selectedBoats.size) return;
  const params = new URLSearchParams();
  selectedBoats.forEach((boatId) => params.append("boats", boatId));
  const start = document.getElementById("window-start").value;
  const end = document.getElementById("window-end").value;
  if (start) params.append("t0", new Date(start).toISOString());
  if (end) params.append("t1", new Date(end).toISOString());
  const tracks = await fetchJSON(`${API_BASE}/tracks?${params.toString()}`);
  let bounds = null;
  tracks.forEach((track) => {
    const latlngs = track.points.map((point) => [point.lat, point.lon]);
    const existing = boatLayers.get(track.boat_id);
    if (existing) {
      map.removeLayer(existing);
      boatLayers.delete(track.boat_id);
    }
    if (!latlngs.length) return;
    const color = boats.find((boat) => boat.id === track.boat_id)?.label_color || "#1f77b4";
    const polyline = L.polyline(latlngs, { color, weight: 3 }).addTo(map);
    boatLayers.set(track.boat_id, polyline);
    const trackBounds = polyline.getBounds();
    bounds = bounds ? bounds.extend(trackBounds) : trackBounds;
  });
  if (bounds) {
    map.fitBounds(bounds.pad(0.2));
  }
}

async function refreshStats() {
  if (!selectedBoats.size) return;
  const start = document.getElementById("window-start").value;
  const end = document.getElementById("window-end").value;
  if (!start || !end) return;
  const params = new URLSearchParams();
  selectedBoats.forEach((boatId) => params.append("boats", boatId));
  params.append("t0", new Date(start).toISOString());
  params.append("t1", new Date(end).toISOString());
  params.append("ref", "twd");
  const stats = await fetchJSON(`${API_BASE}/stats?${params.toString()}`);
  const tbody = document.querySelector("#stats-table tbody");
  tbody.innerHTML = "";
  stats.forEach((stat) => {
    const boat = boats.find((b) => b.id === stat.boat_id);
    const row = document.createElement("tr");
    const cells = [
      boat?.sail_no || stat.boat_id,
      stat.avg_sog.toFixed(2),
      stat.avg_vmg.toFixed(2),
      stat.avg_heading.toFixed(1),
      stat.heading_std.toFixed(1),
      stat.distance_sailed.toFixed(0),
      stat.height_gain.toFixed(1),
      stat.tack_count,
      stat.gybe_count,
    ];
    cells.forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    });
    tbody.appendChild(row);
  });
}

async function downloadCSV() {
  if (!selectedBoats.size) return;
  const start = document.getElementById("window-start").value;
  const end = document.getElementById("window-end").value;
  if (!start || !end) return;
  const params = new URLSearchParams();
  selectedBoats.forEach((boatId) => params.append("boats", boatId));
  params.append("t0", new Date(start).toISOString());
  params.append("t1", new Date(end).toISOString());
  const response = await fetch(`${API_BASE}/export/csv?${params.toString()}`);
  if (!response.ok) {
    alert("Failed to download CSV");
    return;
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "window_stats.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

function initForms() {
  const raceForm = document.getElementById("race-form");
  raceForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(raceForm);
    const payload = {
      name: formData.get("name"),
      start_time: new Date(formData.get("start_time")).toISOString(),
      twd_deg: formData.get("twd") ? Number(formData.get("twd")) : null,
      tws_kt: formData.get("tws") ? Number(formData.get("tws")) : null,
    };
    try {
      await fetchJSON(`${API_BASE}/race`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      raceForm.reset();
      await loadRaces();
    } catch (error) {
      alert(`Failed to create race: ${error.message}`);
    }
  });

  const uploadForm = document.getElementById("upload-form");
  uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!selectedRaceId) {
      alert("Select a race first");
      return;
    }
    const status = document.getElementById("upload-status");
    status.textContent = "Uploading…";
    const formData = new FormData();
    const files = document.getElementById("gpx-files").files;
    Array.from(files).forEach((file) => formData.append("files", file));
    formData.append("race_id", selectedRaceId);
    try {
      await fetchJSON(`${API_BASE}/uploads`, {
        method: "POST",
        body: formData,
      });
      status.textContent = "Upload complete";
      document.getElementById("gpx-files").value = "";
      await loadBoats();
    } catch (error) {
      status.textContent = `Upload failed: ${error.message}`;
    }
  });

  document.getElementById("refresh-stats").addEventListener("click", () => {
    refreshTracks();
    refreshStats();
  });

  document.getElementById("download-csv").addEventListener("click", downloadCSV);
}

function initWindowDefaults() {
  const startInput = document.getElementById("window-start");
  const endInput = document.getElementById("window-end");
  const now = new Date();
  startInput.value = formatDateTimeLocal(now.toISOString());
  endInput.value = formatDateTimeLocal(new Date(now.getTime() + 10 * 60 * 1000).toISOString());
}

async function bootstrap() {
  initForms();
  initWindowDefaults();
  await loadRaces();
}

document.addEventListener("DOMContentLoaded", bootstrap);
