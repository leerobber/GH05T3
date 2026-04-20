import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  timeout: 120000,
});

export const fetchState = () => api.get("/state").then((r) => r.data);
export const postChat = (message, session_id) =>
  api.post("/chat", { message, session_id }).then((r) => r.data);
export const getHistory = (session_id) =>
  api.get("/chat/history", { params: { session_id } }).then((r) => r.data);
export const runKairosCycle = () => api.post("/kairos/cycle").then((r) => r.data);
export const runNightly = () => api.post("/training/nightly").then((r) => r.data);
export const pclTick = (state) =>
  api.post("/pcl/tick", null, { params: { state } }).then((r) => r.data);
export const resetState = () => api.post("/state/reset").then((r) => r.data);
