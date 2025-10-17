export class MapView {
  constructor(elementId = "map") {
    this.layers = new Map();
    this.map = L.map(elementId, { zoomControl: true });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap contributors",
    }).addTo(this.map);
    this.map.setView([0, 0], 2);
  }

  updateTracks(tracks, boatLookup) {
    let bounds = null;
    tracks.forEach((track) => {
      const latlngs = track.points.map((point) => [point.lat, point.lon]);
      const existing = this.layers.get(track.boat_id);
      if (existing) {
        this.map.removeLayer(existing);
        this.layers.delete(track.boat_id);
      }
      if (!latlngs.length) {
        return;
      }
      const color = boatLookup(track.boat_id)?.label_color || "#1f77b4";
      const polyline = L.polyline(latlngs, { color, weight: 3 }).addTo(this.map);
      this.layers.set(track.boat_id, polyline);
      const trackBounds = polyline.getBounds();
      bounds = bounds ? bounds.extend(trackBounds) : trackBounds;
    });
    if (bounds) {
      this.map.fitBounds(bounds.pad(0.2));
    }
  }

  clearMissing(activeBoatIds) {
    Array.from(this.layers.keys()).forEach((boatId) => {
      if (!activeBoatIds.includes(boatId)) {
        const layer = this.layers.get(boatId);
        if (layer) {
          this.map.removeLayer(layer);
        }
        this.layers.delete(boatId);
      }
    });
  }
}
