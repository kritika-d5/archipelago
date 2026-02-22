import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
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
