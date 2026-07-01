---
name: run-gh05t3
description: Run, drive, health-check, and interact with the full GH05T3 / Avery sovereign AI stack. Use when asked to run, start, launch, screenshot, smoke-test, or drive GH05T3 — includes full service health map, swarm agent delegation, Avery chat, KAIROS evolutionary cycles, memory palace queries, training and continuous learner status, and LLM cascade verification. Triggers on: "run gh05t3", "start the stack", "check the services", "is Avery alive", "delegate to swarm", "kairos cycles", "memory query", "training status", "cascade test".
---

GH05T3 is a multi-service sovereign AI stack (FastAPI backend + gateway + React frontend + MongoDB + Ollama). An agent drives it via `driver.py` — a rich Python CLI that covers every layer: service health, Avery chat, swarm delegation, KAIROS cycles, memory palace queries, LLM cascade testing, and training status. The driver auto-loads `backend/.env` and re-execs itself under `backend/.venv` so all imports are available without any manual venv activation.

All paths below are relative to `C:\Users\leer4\GH05T3\`.

---

## Architecture quick-reference

| Port  | Service                   | Role                                             |
|-------|---------------------------|--------------------------------------------------|
| 27017 | MongoDB                   | Economy data, conversation history               |
| 8001  | `backend/server.py`       | Economy engine: KAIROS, memory, training, Telegram |
| 8002  | `backend/gateway_v3.py`   | SwarmBus + all 6 specialist agents + MCP + Avery |
| 3210  | Frontend static server    | React dashboard (built bundle)                   |
| 8010  | `backend/gh05t3_inference.py` | Fine-tuned LoRA model (RTX 5050)            |
| 8011  | llama.cpp verifier        | Radeon 780M iGPU inference                       |
| 8012  | llama.cpp CPU fallback    | Ryzen 7 CPU inference                            |
| 11434 | Ollama                    | Local LLM (qwen2.5:7b default)                   |

**Swarm agents** (all in gateway_v3): ORACLE (research) · FORGE (code gen) · CODEX (code review) · SENTINEL (security) · NEXUS (orchestration) · CHRONICLE (training data harvester)

**LLM cascade** (cost_free_only=1): gh05t3:8010 → Ollama → Groq → Gemini (Anthropic blocked)

---

## Prerequisites

Windows with Python 3.12 and the backend venv already set up. No additional installs needed — the driver re-execs under `backend\.venv\Scripts\python.exe` automatically.

```powershell
# Verify the venv exists (one-time setup if missing):
# Run native\windows\install.ps1 as Administrator

# Check it's there:
Test-Path backend\.venv\Scripts\python.exe
```

---

## Setup

All configuration lives in `backend/.env`. The driver reads it automatically. Key vars:

```
LLM_PROVIDER=ollama          # ollama | gh05t3 | anthropic
LLM_MODEL=qwen2.5:7b         # model to use with Ollama
COST_FREE_ONLY=1             # 1 = never call Anthropic/paid APIs
ENABLE_OPS=1                 # 1 = auto-start herald + cmd_listener
GH05T3_API_TOKEN=            # empty = open/dev mode (no bearer auth)
ANTHROPIC_API_KEY=sk-ant-... # needed for Codex-powered swarm agents
```

---

## Run (agent path)

Drive the stack with the driver from the repo root:

```powershell
cd C:\Users\leer4\GH05T3

# Full service topology health check (TCP + HTTP + zombie detection)
python .Codex\skills\run-gh05t3\driver.py health

# Full integration smoke test — every layer
python .Codex\skills\run-gh05t3\driver.py smoke

# Chat with Avery (tries gateway first, falls back to backend)
python .Codex\skills\run-gh05t3\driver.py chat "What is the sovereign mission?"

# Delegate a task to the specialist swarm
python .Codex\skills\run-gh05t3\driver.py swarm "Security review the payments module"

# List swarm agents with live stats
python .Codex\skills\run-gh05t3\driver.py agents

# Avery identity card + team roster
python .Codex\skills\run-gh05t3\driver.py avery

# Recent KAIROS evolutionary cycles (falls back to JSONL if services are down)
python .Codex\skills\run-gh05t3\driver.py kairos

# Query the memory palace (falls back to SQLite if services are down)
python .Codex\skills\run-gh05t3\driver.py memory "sovereign economy"

# Test the full LLM cascade chain — verified Ollama responds in ~32s
python .Codex\skills\run-gh05t3\driver.py cascade

# Training + continuous learner state (no service required — reads state files)
python .Codex\skills\run-gh05t3\driver.py train
```

### Driver command table

| Command         | What it does                                          | Works offline? |
|-----------------|-------------------------------------------------------|----------------|
| `health`        | TCP + HTTP health for all 9 services, zombie detection, LLM config | Yes (TCP-only) |
| `smoke`         | Full integration test — every service + every layer   | Partial        |
| `chat <msg>`    | Send message to Avery; tries gateway → backend        | No             |
| `swarm <task>`  | Delegate task to specialist swarm via `/swarm/delegate` | No            |
| `agents`        | List agents from `/swarm/agents`                      | No             |
| `avery`         | `/avery` + `/avery/team` identity cards               | No             |
| `kairos`        | Recent KAIROS cycles; falls back to `evolution/kairos_log.jsonl` | Yes (JSONL) |
| `memory <q>`    | Memory palace query; falls back to SQLite direct      | Yes (SQLite)   |
| `cascade`       | Test gh05t3:8010 + Ollama + reads LLM config          | Partial        |
| `train`         | Continuous learner state, SPIN dataset, LoRA adapter  | Yes (files)    |

---

## Run (human path)

```bat
# From repo root — starts MongoDB, backend, gateway, frontend, Ollama, voice listener
run.bat
# → opens http://localhost:3210 in browser after 5s
# → V3SecretsModal pops up if ANTHROPIC_API_KEY / GITHUB_PAT not set
```

---

## Test

```powershell
cd C:\Users\leer4\GH05T3
python -m pytest tests\ -v --timeout=30 2>&1
```

---

## Verified live output (2026-06-02)

**`health` on current running instance:**
```
✓ MongoDB                  :27017  TCP open
⚠ backend (economy)        :8001  TCP open, HTTP timeout — event loop likely blocked
⚠ gateway_v3 (swarm)       :8002  ZOMBIE — netstat LISTENING but TCP refuses. Restart required.
✓ frontend                 :3210  TCP open
✓ Ollama                   :11434  HTTP 200  0.23.2
LLM  provider=ollama  model=qwen2.5:7b  cost_free_only=1
```

**`train`:**
```
Continuous Learner:
  domain=frontier (9/11)  cycles=615  spin_pairs=0  uploads=0
SPIN dataset: data/spin_dataset.jsonl  (650 pairs)
LoRA adapter: backend/models/gh05t3_lora_adapter  (2 files, 0.0 MB)
```

**`cascade`:**
```
✗ gh05t3-inference     :8010  Down
✓ Ollama               :11434  31.8s  Pong!
Active cascade: provider=ollama  model=qwen2.5:7b  cost_free_only=True
```

**Ollama models loaded:** `deepseek-r1:7b`, `moondream:latest`, `avery-sovereign:latest`, `codex-sovereign:latest`, `sentinel-sovereign:latest`

---

## Gotchas

- **Backend event loop blocks on slow Ollama calls.** `server.py` at :8001 accepts TCP but hangs on HTTP — the uvicorn event loop is blocked waiting for qwen2.5:7b (~32s per response). `/api/health` appears broken; use TCP probe to confirm the process is alive, then just wait it out or restart.

- **Gateway zombie-listen.** `gateway_v3.py` at :8002 can enter a state where `netstat` shows LISTENING but all new connections are refused or hang indefinitely. Root cause: uvicorn's internal lifespan startup failed (SwarmBus boot, peer discovery, or MCP mount error), leaving the socket bound but the accept loop dead. **`run.bat`'s own kill logic can fail to terminate these zombies** — the `taskkill /F /PID` in the port-clearing loop silently exits 0 even when it fails. Manual fix: `Stop-Process -Id <PID> -Force` where PID comes from `netstat -ano | Select-String ":8002"`. Then re-run `run.bat`.

- **Never use PowerShell `Invoke-RestMethod` to probe 8002.** On Windows, PowerShell routes `127.0.0.1` through `::ffff:127.0.0.1` (IPv6-mapped). If uvicorn is in zombie state, this always shows "connection refused" even when raw TCP to `127.0.0.1:8002` succeeds. Use the driver or Python `requests` from the backend venv.

- **8010 (gh05t3_inference) not started by `run.bat` unconditionally.** It launches in a separate `cmd` window; if RTX 5050 PyTorch is not `cu128`, the process crashes silently. Check `backend/models/gh05t3_lora_adapter/` — if empty (0 bytes adapter), training was never completed. Run `native\windows\train.bat` first.

- **LoRA adapter at 0 bytes is normal before first training run.** The directory exists (created by git or install.ps1) but the adapter files are empty placeholders. `gh05t3_inference.py` will crash on load. Set `LLM_PROVIDER=ollama` in `backend/.env` until training completes.

- **COST_FREE_ONLY=1 blocks Anthropic.** With this set, `ghost_llm.py` never calls Anthropic even if `ANTHROPIC_API_KEY` is present. Swarm agents that need Codex (ClaudeSwarmAgent in gateway_v3) will degrade to Ollama. Set `COST_FREE_ONLY=0` and `ALLOW_PAID_LLM=1` in `backend/.env` to unlock.

- **8011 (llama verifier) shows TCP open but HTTP timeout.** Something is binding port 8011 (PID 4088 + 31720 per live netstat) but it's not the llama.cpp verifier — it's likely the phi_service or NPU service from a separate stack. The driver correctly reports "HTTP timeout".

- **GH05T3_API_TOKEN empty = open/dev mode.** The gateway runs without bearer auth. Any caller on the LAN can hit the API. Set `GH05T3_API_TOKEN` in `backend/.env` for remote security.

- **Frontend at 3210 is a static build.** Changes to `frontend/src/` require `REACT_APP_GW3_URL=http://localhost:8002 yarn build` before they appear. The Python http.server just serves whatever is in `frontend/build/`.

---

## Troubleshooting

- **`driver.py` crashes with `UnicodeEncodeError`**: Windows stdout defaulting to cp1252. Fixed in driver (re-wraps stdout as UTF-8). Symptom: happens on the `─` or `—` characters. The driver now self-heals this on startup.

- **`driver.py` hangs on `cascade`**: Ollama is loading a model cold (first request). qwen2.5:7b takes ~32 seconds on RTX 5050 with 8GB VRAM. Wait or kill and retry.

- **`chat` returns nothing from both gateway and backend**: Gateway is in zombie state AND backend event loop is blocked. First run `Stop-Process -Id (netstat -ano | Select-String ":8001|:8002" | ForEach-Object { ($_ -split "\s+")[-1] } | Sort-Object -Unique) -Force` to kill zombies, then re-run `run.bat`.

- **`kairos` shows `score=0.10, REVISE` only**: The backend ran one KAIROS cycle but it was degraded (all LLM backends offline at cycle time → score 0.1). Normal until Ollama is warm and a real cycle runs.

- **`memory sovereign` → "No results"**: Memory palace (SQLite) exists but has 0 shards. Shards are written by the backend's memory engine during active conversations. Start the stack and have at least one chat session.

- **`swarm` or `agents` → "Gateway unreachable"**: Gateway at 8002 is in zombie state. Run `run.bat` to restart.

- **`train.bat` fails with "sm_120 not supported"**: PyTorch version is < 2.6. RTX 5050 is Blackwell (sm_120) and requires `cu128`. Reinstall: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128`.
