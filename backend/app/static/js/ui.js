import { formatDateTimeLocal } from "./utils.js";

export class UIController {
  constructor(apiClient, state, mapView) {
    this.api = apiClient;
    this.state = state;
    this.mapView = mapView;
  }

  async initialize() {
    this.cacheDom();
    this.registerEventListeners();
    this.setupSubscriptions();
    this.initWindowDefaults();
    await this.loadRaces();
  }

  cacheDom() {
    this.raceForm = document.getElementById("race-form");
    this.raceList = document.getElementById("race-list");
    this.uploadForm = document.getElementById("upload-form");
    this.uploadFiles = document.getElementById("gpx-files");
    this.uploadStatus = document.getElementById("upload-status");
    this.uploadRaceSelect = document.getElementById("upload-race");
    this.boatList = document.getElementById("boat-list");
    this.windowStart = document.getElementById("window-start");
    this.windowEnd = document.getElementById("window-end");
    this.refreshButton = document.getElementById("refresh-stats");
    this.downloadButton = document.getElementById("download-csv");
    this.statsTableBody = document.querySelector("#stats-table tbody");
  }

  registerEventListeners() {
    this.raceForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(this.raceForm);
      const payload = {
        name: formData.get("name"),
        start_time: new Date(formData.get("start_time")).toISOString(),
        twd_deg: formData.get("twd") ? Number(formData.get("twd")) : null,
        tws_kt: formData.get("tws") ? Number(formData.get("tws")) : null,
      };
      try {
        await this.api.createRace(payload);
        this.raceForm.reset();
        await this.loadRaces();
      } catch (error) {
        alert(`Failed to create race: ${error.message}`);
      }
    });

    this.raceList.addEventListener("click", (event) => {
      if (event.target instanceof HTMLButtonElement) {
        const raceId = Number.parseInt(event.target.dataset.id, 10);
        if (!Number.isNaN(raceId)) {
          this.state.setSelectedRace(raceId);
        }
      }
    });

    this.uploadRaceSelect.addEventListener("change", () => {
      const raceId = Number.parseInt(this.uploadRaceSelect.value, 10);
      if (!Number.isNaN(raceId)) {
        this.state.setSelectedRace(raceId);
      }
    });

    this.uploadForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const raceId = this.state.selectedRaceId;
      if (!raceId) {
        alert("Select a race first");
        return;
      }
      const files = Array.from(this.uploadFiles.files || []);
      if (!files.length) {
        alert("Choose at least one GPX file");
        return;
      }
      const formData = new FormData();
      files.forEach((file) => formData.append("files", file));
      formData.append("race_id", raceId);
      this.setUploadStatus("Uploading…");
      try {
        await this.api.uploadTracks(formData);
        this.uploadFiles.value = "";
        this.setUploadStatus("Upload complete");
        await this.loadBoats();
      } catch (error) {
        this.setUploadStatus(`Upload failed: ${error.message}`);
      }
    });

    this.refreshButton.addEventListener("click", () => {
      this.refreshData();
    });

    this.downloadButton.addEventListener("click", () => {
      this.downloadCsv();
    });
  }

  setupSubscriptions() {
    this.state.on("races", (races) => {
      this.renderRaceList(races);
      if (races.length && !this.state.selectedRaceId) {
        this.state.setSelectedRace(races[0].id);
      }
    });

    this.state.on("selectedRace", (raceId) => {
      if (raceId) {
        this.uploadRaceSelect.value = String(raceId);
        this.prefillWindow(raceId);
        this.loadBoats();
      }
    });

    this.state.on("boats", (boats) => {
      this.renderBoatList(boats);
    });

    this.state.on("boatSelection", (boatIds) => {
      this.mapView.clearMissing(boatIds);
      if (boatIds.length) {
        this.refreshData();
      } else {
        this.clearStatsTable();
      }
    });
  }

  async loadRaces() {
    const races = await this.api.listRaces();
    this.state.setRaces(races);
  }

  async loadBoats() {
    if (!this.state.selectedRaceId) return;
    const boats = await this.api.listBoats(this.state.selectedRaceId);
    this.state.setBoats(boats);
  }

  renderRaceList(races) {
    this.raceList.innerHTML = "";
    this.uploadRaceSelect.innerHTML = "";
    races.forEach((race) => {
      const wrapper = document.createElement("div");
      wrapper.className = "race-item";
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.id = String(race.id);
      button.textContent = race.name;
      wrapper.appendChild(button);
      this.raceList.appendChild(wrapper);

      const option = document.createElement("option");
      option.value = race.id;
      option.textContent = race.name;
      this.uploadRaceSelect.appendChild(option);
    });
    if (this.state.selectedRaceId) {
      this.uploadRaceSelect.value = String(this.state.selectedRaceId);
    }
  }

  renderBoatList(boats) {
    this.boatList.innerHTML = "";
    boats.forEach((boat) => {
      const div = document.createElement("div");
      div.className = "boat-item";
      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = boat.id;
      checkbox.addEventListener("change", () => {
        this.state.toggleBoat(boat.id, checkbox.checked);
      });
      const swatch = document.createElement("span");
      swatch.className = "boat-swatch";
      swatch.style.background = boat.label_color;
      label.append(checkbox, swatch, document.createTextNode(boat.sail_no));
      div.appendChild(label);
      this.boatList.appendChild(div);
    });
  }

  getWindowRange() {
    const start = this.windowStart.value;
    const end = this.windowEnd.value;
    if (!start || !end) {
      return null;
    }
    const startIso = new Date(start).toISOString();
    const endIso = new Date(end).toISOString();
    return { startIso, endIso };
  }

  async refreshData() {
    try {
      await Promise.all([this.refreshTracks(), this.refreshStats()]);
    } catch (error) {
      console.error("Failed to refresh data", error);
      alert(`Failed to refresh data: ${error.message}`);
    }
  }

  async refreshTracks() {
    const boatIds = this.state.getSelectedBoats();
    if (!boatIds.length) return;
    const range = this.getWindowRange();
    const params = { boats: boatIds };
    if (range?.startIso) params.t0 = range.startIso;
    if (range?.endIso) params.t1 = range.endIso;
    const tracks = await this.api.getTracks(params);
    this.mapView.updateTracks(tracks, (boatId) => this.state.getBoatById(boatId));
  }

  async refreshStats() {
    const boatIds = this.state.getSelectedBoats();
    const range = this.getWindowRange();
    if (!boatIds.length || !range) {
      this.clearStatsTable();
      return;
    }
    const stats = await this.api.getStats({
      boats: boatIds,
      t0: range.startIso,
      t1: range.endIso,
      ref: "twd",
    });
    this.renderStatsTable(stats);
  }

  renderStatsTable(stats) {
    this.statsTableBody.innerHTML = "";
    stats.forEach((stat) => {
      const row = document.createElement("tr");
      const boat = this.state.getBoatById(stat.boat_id);
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
      this.statsTableBody.appendChild(row);
    });
  }

  clearStatsTable() {
    this.statsTableBody.innerHTML = "";
  }

  async downloadCsv() {
    const boatIds = this.state.getSelectedBoats();
    const range = this.getWindowRange();
    if (!boatIds.length || !range) {
      alert("Select boats and a valid time window first");
      return;
    }
    try {
      const blob = await this.api.downloadCsv({
        boats: boatIds,
        t0: range.startIso,
        t1: range.endIso,
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "window_stats.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      alert(error.message);
    }
  }

  initWindowDefaults() {
    const now = new Date();
    this.windowStart.value = formatDateTimeLocal(now.toISOString());
    this.windowEnd.value = formatDateTimeLocal(new Date(now.getTime() + 10 * 60 * 1000).toISOString());
  }

  prefillWindow(raceId) {
    const race = this.state.getRaceById(raceId);
    if (!race) return;
    const start = new Date(race.start_time);
    this.windowStart.value = formatDateTimeLocal(start.toISOString());
    this.windowEnd.value = formatDateTimeLocal(new Date(start.getTime() + 5 * 60 * 1000).toISOString());
  }

  setUploadStatus(text) {
    this.uploadStatus.textContent = text;
  }
}
