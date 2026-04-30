import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8001";
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

// --- Phase 7: Ollama · Coder · Setup nudge · Embeddings ---
export const setupStatus = () => api.get("/setup/status").then((r) => r.data);
export const embeddingsStatus = () => api.get("/embeddings/status").then((r) => r.data);
export const ollamaStatus = () => api.get("/ollama/status").then((r) => r.data);
export const ollamaConfigure = (gateway_url) =>
  api.post("/ollama/configure", { gateway_url }).then((r) => r.data);
export const ollamaPull = (model) =>
  api.post("/ollama/pull", { model }).then((r) => r.data);
export const coderRepos = () => api.get("/coder/repos").then((r) => r.data);
export const coderRun = (payload) => api.post("/coder/task", payload).then((r) => r.data);
export const coderRuns = (limit = 10) =>
  api.get("/coder/runs", { params: { limit } }).then((r) => r.data);

// --- Phase 1 (SA³): Swarm ---
export const swarmState = () => api.get("/swarm/state").then((r) => r.data);
export const swarmRun = (task_type, prompt, expected_flag = null) =>
  api.post("/swarm/run", { task_type, prompt, expected_flag }).then((r) => r.data);
export const swarmValidate = (n = 20) =>
  api.post("/swarm/validate", { n }).then((r) => r.data);
export const swarmReset = () => api.post("/swarm/reset").then((r) => r.data);
export const swarmLedger = (limit = 30) =>
  api.get("/swarm/ledger", { params: { limit } }).then((r) => r.data);

export const wsUrl = () => {
  const base = BACKEND_URL.replace(/^http/, "ws");
  return `${base}/api/ws`;
};

// --- v3 Gateway (SwarmBus · Claude · GitHub) ---
const GW3_URL = process.env.REACT_APP_GW3_URL || "http://localhost:8002";
export const gw3 = axios.create({ baseURL: GW3_URL, timeout: 60000 });

export const gw3WsUrl = () => GW3_URL.replace(/^http/, "ws") + "/ws";

export const gw3Health      = () => gw3.get("/health").then((r) => r.data);
export const gw3Agents      = () => gw3.get("/swarm/agents").then((r) => r.data);
export const gw3Delegate    = (task, agent = null) =>
  gw3.post("/swarm/delegate", { task, agent }).then((r) => r.data);
export const gw3Convos      = (n = 80, channel = null, src = null) =>
  gw3.get("/conversations", { params: { n, channel, src } }).then((r) => r.data);
export const gw3ConvoSearch = (q) =>
  gw3.get("/conversations/search", { params: { q } }).then((r) => r.data);
export const gw3GithubStatus = () => gw3.get("/github/status").then((r) => r.data);
export const gw3GithubSyncMemory = () =>
  gw3.post("/github/sync-memory").then((r) => r.data);
export const gw3ClaudeTrain  = (domain = "agent_systems", count = 5) =>
  gw3.post("/claude/train", { domain, count }).then((r) => r.data);
export const gw3ClaudeReview = (module, source = "") =>
  gw3.post("/claude/review", { module, source }).then((r) => r.data);
export const gw3KairosElite    = () => gw3.get("/kairos/elite").then((r) => r.data);
export const gw3SecretsStatus  = () => gw3.get("/setup/secrets/status").then((r) => r.data);
export const gw3SaveSecrets    = (anthropic_api_key, github_pat) =>
  gw3.post("/setup/secrets", { anthropic_api_key, github_pat }).then((r) => r.data);
