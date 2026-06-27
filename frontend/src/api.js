const API_BASE =
  import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? "" : "http://127.0.0.1:8000");

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  return response.json();
}

export const api = {
  health: () => request("/api/health"),
  customers: () => request("/api/customers"),
  startCall: (payload) =>
    request("/api/calls/start", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  respond: (payload) =>
    request("/api/agent/respond", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  calls: () => request("/api/calls"),
  callDetail: (id) => request(`/api/calls/${id}`),
  analytics: () => request("/api/analytics/summary"),
  policies: () => request("/api/policies"),
};
