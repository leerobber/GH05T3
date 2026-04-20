import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, timeout: 180000 });

export const fetchState = () => api.get("/state").then((r) => r.data);
export const postChat = (message, session_id) =>
  api.post("/chat", { message, session_id }).then((r) => r.data);
export const getHistory = (session_id) =>
  api.get("/chat/history", { params: { session_id } }).then((r) => r.data);
export const runKairosCycle = () => api.post("/kairos/cycle").then((r) => r.data);
export const kairosRecent = () => api.get("/kairos/recent").then((r) => r.data);
export const runNightly = () => api.post("/training/nightly").then((r) => r.data);
export const pclTick = (state) =>
  api.post("/pcl/tick", null, { params: { state } }).then((r) => r.data);
export const hcmCloud = () => api.get("/hcm/cloud").then((r) => r.data);
export const runGhostScript = (source) =>
  api.post("/ghostscript/run", { source }).then((r) => r.data);
export const demoGhostScript = () => api.get("/ghostscript/demo").then((r) => r.data);
export const cassandraRun = (scenario) =>
  api.post("/cassandra", { scenario }).then((r) => r.data);
export const stegoEncode = (secret, cover) =>
  api.post("/stego/encode", { secret, cover }).then((r) => r.data);
export const stegoDecode = (covertext, byte_count) =>
  api.post("/stego/decode", { covertext, byte_count }).then((r) => r.data);
export const stegoCover = () => api.get("/stego/cover").then((r) => r.data);
export const tgConfigure = (cfg) =>
  api.post("/telegram/configure", cfg).then((r) => r.data);
export const tgStart = () => api.post("/telegram/start").then((r) => r.data);
export const tgStop = () => api.post("/telegram/stop").then((r) => r.data);
export const tgStatus = () => api.get("/telegram/status").then((r) => r.data);
export const schedulerToggle = (enable) =>
  api.post("/scheduler/toggle", null, { params: { enable } }).then((r) => r.data);

export const wsUrl = () => {
  const base = BACKEND_URL.replace(/^http/, "ws");
  return `${base}/api/ws`;
};
