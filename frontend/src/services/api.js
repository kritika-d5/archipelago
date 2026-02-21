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
