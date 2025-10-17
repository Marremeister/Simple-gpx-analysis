const DEFAULT_BASE = () => {
  if (window.API_BASE) {
    return window.API_BASE;
  }
  return `${window.location.origin}/api`;
};

export class ApiClient {
  constructor(baseUrl = DEFAULT_BASE()) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  async request(path, options = {}) {
    const response = await fetch(`${this.baseUrl}${path}`, options);
    if (!response.ok) {
      let detail;
      try {
        const data = await response.json();
        detail = data.detail || response.statusText;
      } catch (error) {
        detail = response.statusText;
      }
      throw new Error(detail);
    }
    if (response.status === 204) {
      return null;
    }
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return response.json();
    }
    return response;
  }

  async createRace(payload) {
    return this.request("/race", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  async listRaces() {
    return this.request("/race");
  }

  async listBoats(raceId) {
    const query = raceId ? `?raceId=${encodeURIComponent(raceId)}` : "";
    return this.request(`/boats${query}`);
  }

  async uploadTracks(formData) {
    return this.request("/uploads", {
      method: "POST",
      body: formData,
    });
  }

  async getTracks(params) {
    const search = new URLSearchParams();
    if (params.boats) {
      params.boats.forEach((boatId) => search.append("boats", boatId));
    }
    if (params.t0) search.append("t0", params.t0);
    if (params.t1) search.append("t1", params.t1);
    if (params.downsample) search.append("downsample", params.downsample);
    return this.request(`/tracks?${search.toString()}`);
  }

  async getStats(params) {
    const search = new URLSearchParams();
    params.boats.forEach((boatId) => search.append("boats", boatId));
    search.append("t0", params.t0);
    search.append("t1", params.t1);
    search.append("ref", params.ref ?? "twd");
    if (params.legId) search.append("legId", params.legId);
    return this.request(`/stats?${search.toString()}`);
  }

  async downloadCsv(params) {
    const search = new URLSearchParams();
    params.boats.forEach((boatId) => search.append("boats", boatId));
    search.append("t0", params.t0);
    search.append("t1", params.t1);
    if (params.ref) search.append("ref", params.ref);

    const response = await fetch(`${this.baseUrl}/export/csv?${search.toString()}`);
    if (!response.ok) {
      throw new Error("Failed to download CSV");
    }
    return response.blob();
  }
}
