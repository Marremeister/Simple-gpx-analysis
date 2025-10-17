import { ApiClient } from "./apiClient.js";
import { MapView } from "./mapView.js";
import { AppState } from "./state.js";
import { UIController } from "./ui.js";

const api = new ApiClient();
const state = new AppState();
const mapView = new MapView("map");
const ui = new UIController(api, state, mapView);

document.addEventListener("DOMContentLoaded", () => {
  ui.initialize().catch((error) => {
    console.error("Failed to initialise UI", error);
  });
});
