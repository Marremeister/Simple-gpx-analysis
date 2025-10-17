export class AppState {
  constructor() {
    this.races = [];
    this.boats = [];
    this.selectedRaceId = null;
    this.selectedBoats = new Set();
    this.listeners = new Map();
  }

  on(event, handler) {
    const current = this.listeners.get(event) || [];
    current.push(handler);
    this.listeners.set(event, current);
  }

  emit(event, payload) {
    const handlers = this.listeners.get(event) || [];
    handlers.forEach((handler) => handler(payload));
  }

  setRaces(races) {
    this.races = races;
    this.emit("races", races);
  }

  setSelectedRace(raceId) {
    if (this.selectedRaceId === raceId) {
      return;
    }
    this.selectedRaceId = raceId;
    this.selectedBoats.clear();
    this.emit("selectedRace", raceId);
    this.emit("boatSelection", this.getSelectedBoats());
  }

  setBoats(boats) {
    this.boats = boats;
    this.selectedBoats.clear();
    this.emit("boats", boats);
    this.emit("boatSelection", this.getSelectedBoats());
  }

  toggleBoat(boatId, enabled) {
    if (enabled) {
      this.selectedBoats.add(boatId);
    } else {
      this.selectedBoats.delete(boatId);
    }
    this.emit("boatSelection", this.getSelectedBoats());
  }

  getSelectedBoats() {
    return Array.from(this.selectedBoats);
  }

  getRaceById(id) {
    return this.races.find((race) => race.id === id) || null;
  }

  getBoatById(id) {
    return this.boats.find((boat) => boat.id === id) || null;
  }
}
