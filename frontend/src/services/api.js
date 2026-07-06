import axios from "axios";

const baseURL =
  process.env.REACT_APP_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

const api = axios.create({
  baseURL,
});

// Per-browser session identity. Isolates this browser's GitHub/Notion connection (and,
// later, its saved graphs) from every other visitor. Generated once, persisted in
// localStorage so it survives reloads and the OAuth redirect round-trip. Must match the
// backend's X-Session-Id validation format: [A-Za-z0-9_-]{8,128}.
const SESSION_KEY = "archipelago_session_id";

export function getSessionId() {
  let id = null;
  try {
    id = localStorage.getItem(SESSION_KEY);
  } catch {
    // localStorage unavailable (private mode / blocked) — fall through to a fresh id.
  }
  if (!id) {
    id =
      (typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `s-${Date.now()}-${Math.random().toString(36).slice(2)}`
      ).replace(/[^A-Za-z0-9_-]/g, "");
    try {
      localStorage.setItem(SESSION_KEY, id);
    } catch {
      // Can't persist; the in-memory id still isolates this page load.
    }
  }
  return id;
}

api.interceptors.request.use((config) => {
  config.headers["X-Session-Id"] = getSessionId();
  return config;
});

export default api;

// Architecture Studio API functions
export const generateArchitectureBlueprint = async (payload) => {
  const response = await api.post("/architecture/generate", payload);
  return response.data;
};

// GitHub Integration API functions
export const connectGitHub = async (payload) => {
  const response = await api.post("/integrations/github/connect", payload);
  return response.data;
};

export const getGitHubRepos = async () => {
  const response = await api.get("/integrations/github/repos");
  return response.data;
};

export const monitorRepoPush = async (repoName, payload) => {
  const response = await api.post(`/integrations/github/monitor/${repoName}`, payload);
  return response.data;
};

export const getPushTimeline = async (repoName) => {
  const response = await api.get(`/integrations/github/timeline/${repoName}`);
  return response.data;
};

// Notion Integration API functions
export const connectNotion = async (payload) => {
  const response = await api.post("/integrations/notion/connect", payload);
  return response.data;
};

export const updateNotionPage = async (payload) => {
  const response = await api.post("/integrations/notion/update", payload);
  return response.data;
};

export const getNotionPages = async () => {
  const response = await api.get("/integrations/notion/pages");
  return response.data;
};

// Documentation Comparison API functions
export const compareDocumentation = async (repoKey, payload) => {
  const response = await api.post(`/query/doc-diff?repo_key=${encodeURIComponent(repoKey)}`, payload);
  return response.data;
};

export const generateDocumentationUpdate = async (repoKey, payload) => {
  const response = await api.post(`/query/doc-update?repo_key=${encodeURIComponent(repoKey)}`, payload);
  return response.data;
};
