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
export const updateEnv = (updates) => api.put("/settings/env", { updates });
export const changePassword = (current_password, new_password) =>
  api.put("/settings/password", { current_password, new_password });

export const uploadPdf = (file) => {
  const form = new FormData();
  form.append("file", file);
  return api.post("/settings/pdf", form, { headers: { "Content-Type": "multipart/form-data" } });
};
export const deletePdf = () => api.delete("/settings/pdf");
export const pdfDownloadUrl = `${API_BASE}/settings/pdf`;

// CRM
export const getCrmMeta = () => api.get("/crm/meta");
export const getLead = (id) => api.get(`/leads/${id}`);
export const updateLead = (id, data) => api.patch(`/leads/${id}`, data);
export const getLeadTimeline = (id) => api.get(`/leads/${id}/timeline`);
export const getPipeline = () => api.get("/pipeline");
export const getDashboardSummary = () => api.get("/dashboard/summary");
export const listTasks = (params = {}) => api.get("/tasks", { params });
export const createTask = (data) => api.post("/tasks", data);
export const updateTask = (id, data) => api.patch(`/tasks/${id}`, data);
export const deleteTask = (id) => api.delete(`/tasks/${id}`);
export const listMeetings = (lead_id) => api.get("/meetings", { params: lead_id ? { lead_id } : {} });
export const createMeeting = (data) => api.post("/meetings", data);
