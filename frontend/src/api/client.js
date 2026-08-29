const API_BASE =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Standard fetch helper that validates HTTP status codes
 * and properly parses JSON responses and detailed error messages.
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  };

  const response = await fetch(url, config);
  let data;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const errorDetail =
      data?.detail ||
      data?.message ||
      `HTTP request to ${endpoint} failed with status ${response.status}`;
    const error = new Error(errorDetail);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

export const api = {
  // -------------------------------------------------------------------------
  // System Status & Database Records
  // -------------------------------------------------------------------------
  getHealth: () => request("/health"),
  getDbStatus: () => request("/db-status"),
  getVerdicts: () => request("/verdicts"),
  triggerCheckoutFailure: async (body = {}) => {
    // Deliberate failure route intentionally returns HTTP 500 with stack trace
    const url = `${API_BASE}/checkout`;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    try {
      return await response.json();
    } catch {
      return { status: "error", message: "Failed to parse checkout response" };
    }
  },

  // -------------------------------------------------------------------------
  // Incidents
  // -------------------------------------------------------------------------
  ingestIncident: (data) =>
    request("/api/v1/ingest", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getIncident: (id) => request(`/api/v1/incidents/${id}`),

  // -------------------------------------------------------------------------
  // Investigation Pipeline
  // -------------------------------------------------------------------------
  collectEvidence: (id, payload = null) =>
    request(`/api/v1/incidents/${id}/collect-evidence`, {
      method: "POST",
      body: payload ? JSON.stringify(payload) : undefined,
    }),
  buildGraph: (id, payload = null) =>
    request(`/api/v1/incidents/${id}/build-graph`, {
      method: "POST",
      body: payload ? JSON.stringify(payload) : undefined,
    }),
  analyzeRca: (id) =>
    request(`/api/v1/incidents/${id}/analyze`, {
      method: "POST",
    }),
  getImpact: (id) =>
    request(`/api/v1/incidents/${id}/impact`, {
      method: "POST",
    }),
  getCandidateFixes: (id) =>
    request(`/api/v1/incidents/${id}/fixes`, {
      method: "POST",
    }),

  // -------------------------------------------------------------------------
  // Human Approval Gate
  // -------------------------------------------------------------------------
  getApproval: (id) => request(`/api/v1/incidents/${id}/approval`),
  submitApproval: (id, data) =>
    request(`/api/v1/incidents/${id}/approval`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // -------------------------------------------------------------------------
  // Regression Sentinel
  // -------------------------------------------------------------------------
  runRegressionCheck: (id, data) =>
    request(`/api/v1/incidents/${id}/regression-check`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // -------------------------------------------------------------------------
  // GitHub PR Integration
  // -------------------------------------------------------------------------
  createGitHubPr: (id, data) =>
    request(`/api/v1/incidents/${id}/github/pr`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

export default api;
