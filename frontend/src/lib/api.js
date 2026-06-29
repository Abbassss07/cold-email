import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

// Helpers
export const login = (password) => api.post("/auth/login", { password });
export const logout = () => api.post("/auth/logout");
export const me = () => api.get("/auth/me");

export const uploadCsv = (file) => {
  const form = new FormData();
  form.append("file", file);
  return api.post("/upload", form, { headers: { "Content-Type": "multipart/form-data" } });
};

export const listEmails = (status) => api.get("/emails", { params: status ? { status } : {} });
export const getStats = () => api.get("/stats");
export const generate = (ids) => api.post("/emails/generate", { ids });
export const regenerate = (id) => api.post(`/emails/${id}/regenerate`);
export const updateEmail = (id, data) => api.patch(`/emails/${id}`, data);
export const deleteEmail = (id) => api.delete(`/emails/${id}`);
export const sendEmails = (ids) => api.post("/emails/send", { ids });

export const getLogs = (params = {}) => api.get("/logs", { params });
export const exportLogsUrl = `${API_BASE}/logs/export`;

export const getSettings = () => api.get("/settings");
export const updateContext = (content) => api.put("/settings/context", { content });
export const updateDailyLimit = (n) => api.put("/settings/daily-limit", { daily_limit: n });
export const changePassword = (current_password, new_password) =>
  api.put("/settings/password", { current_password, new_password });
