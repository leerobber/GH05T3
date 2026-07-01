---
name: omni-build
description: Full Omni Sentinel build — start, verify, and monitor the complete Aethyro/GH05T3 production stack. Use this skill whenever the user wants to: start the full stack, bring up all 17 services, check if everything is running, run the supervisor, start Ollama with sovereign models, verify the build is healthy, run the full test suite, or prepare for a demo. Also triggers on "START_ALL", "bring everything up", "is the stack running", "supervisor status", "all services", "check all ports", "demo mode on/off", "omni sentinel", "full build", "17 services", or any question about starting or verifying the complete Aethyro system. This skill is the single reference for the complete production startup sequence.
---

# Omni Sentinel — Full Aethyro Stack

**Repo**: `C:\Users\leer4\GH05T3\`  
**Supervisor**: port 8090  
**17 managed services** across Windows-native, WSL, and NPU layers  
**Port registry**: `C:\Users\leer4\Documents\PORT_REGISTRY.md`

---

## Full Stack Startup (Production)

```powershell
# 1. KILL port conflicts first (always safe to run)
C:\Users\leer4\GH05T3\native\windows\KILL_PORTS.bat

# 2. Start full stack
C:\Users\leer4\GH05T3\native\windows\START_ALL.bat

# 3. (Optional) Start WSL bridge services
C:\Users\leer4\GH05T3\native\windows\START_WSL.bat
```

`START_ALL.bat` kills ports 8001/8002/8081/8090/8099 before starting supervisor. No manual pre-kill needed if you use `START_ALL.bat`.

---

## Service Registry (17 services)

| Service | Port | Start method | Notes |
|---|---|---|---|
| economy-api | 8081 | supervisor | Agent economy REST API |
| backend | 8001 | supervisor | Main backend (FastAPI) |
| gateway | 8002 | supervisor | gateway_v3.py — mesh routing |
| frontend | 3210 | supervisor | React UI |
| serve | 7861 | supervisor | Ollama proxy + demo mode bypass |
| supervisor | 8090 | self | Process supervisor + health aggregator |
| mongo | 27017 | supervisor | MongoDB |
| payments | 7862 | supervisor | Payment gateway stub |
| landing-server | 8765 | supervisor | Landing page server |
| pipeline-backend | 8099 | supervisor | sovereignnation/pipeline_backend.py |
| npu-embed | 8111 | supervisor | ryzen-ai conda env, MiniLM + BGE-large |
| continuous-learner | — | supervisor | Background learning daemon |
| cmd-listener | — | supervisor | Command/control listener |
| amplifier | — | supervisor | Signal amplifier daemon |
| tunnel-chat | — | supervisor | Cloudflared tunnel (chat) |
| tunnel-landing | — | supervisor | Cloudflared tunnel (landing) |
| tunnel-watcher | — | supervisor | Tunnel health watcher |

### Checking supervisor status

```powershell
# Quick status check — all services
Invoke-RestMethod http://localhost:8090/status | ConvertTo-Json -Depth 4

# Or via curl
curl -s http://localhost:8090/status | python -m json.tool
```

Expected: `"all_ok": true` with `status: "running"` for all 17 entries.

---

## Port Kill Reference

```batch
REM KILL_PORTS.bat — safe to run anytime
C:\Users\leer4\GH05T3\native\windows\KILL_PORTS.bat
```

Kills: 8001, 8002, 8081, 8090, 8099 (the 5 ports most likely to conflict after a crash/restart).

### Manual port kill (PowerShell)

```powershell
# Kill a specific port
$port = 8001
$pid = (Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue).OwningProcess
if ($pid) { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue }

# Kill all managed ports at once
@(8001, 8002, 8081, 8090, 8099, 8111, 7861, 7862, 8765) | ForEach-Object {
    $p = (Get-NetTCPConnection -LocalPort $_ -ErrorAction SilentlyContinue).OwningProcess
    if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue; Write-Host "Killed port $_" }
}
```

---

## Ollama Configuration

Ollama must be running before `START_ALL.bat`. It's a Windows tray app.

```powershell
# Check Ollama is up
curl -s http://localhost:11434/api/tags | python -m json.tool

# Critical env vars (set at User scope — permanent)
[System.Environment]::SetEnvironmentVariable("KEEP_ALIVE", "10m", "User")
[System.Environment]::SetEnvironmentVariable("MAX_LOADED_MODELS", "1", "User")
[System.Environment]::SetEnvironmentVariable("NUM_PARALLEL", "1", "User")
[System.Environment]::SetEnvironmentVariable("FLASH_ATTENTION", "1", "User")
```

### WARNING: Never auto-update Ollama

Ollama tray-app delta updates break GPU (missing CUDA DLLs). The `updates_v2` directory is write-locked to prevent this. Current working version: **0.23.2**. Do NOT run `ollama update` or click update prompts.

### Sovereign models

```powershell
# List loaded models
curl -s http://localhost:11434/api/tags | python -m json.tool

# Expected models:
# avery-sovereign   Q4_K_M 4.68GB  17 tok/s, 72% GPU offload
# forge-sovereign   Q8 1.53GB each
# oracle-sovereign  Q8 1.53GB
# codex-sovereign   Q8 1.53GB
# nexus-sovereign   Q8 1.53GB
# sentinel-sovereign Q8 1.53GB
# gh05t3:latest     (demo model — stays in VRAM from KAIROS cycles)
```

### GPU inference prerequisites

- LM Studio must be CLOSED (eats 4GB VRAM, forces CPU-only fallback)
- RTX Remix kit.exe must be CLOSED (eats VRAM)
- CUDA DLLs confirmed present at: `cuda_v13/ggml-cuda.dll`

---

## NPU Embedding Service

**Port**: 8111  
**Runtime**: ryzen-ai conda env at `C:\Users\leer4\.conda\envs\ryzen-ai-1.7.0\`

```powershell
# Start NPU service (supervisor handles this — manual only for debug)
conda activate ryzen-ai-1.7.0
python C:\Users\leer4\GH05T3\sovereignnation\npu_embedding_service.py

# Health check
curl -s http://localhost:8111/health

# Test embedding
curl -s -X POST http://localhost:8111/embed `
  -H "Content-Type: application/json" `
  -d '{"texts": ["test embedding"]}' | python -m json.tool

# Test intent routing (oracle/forge/codex/nexus)
curl -s -X POST http://localhost:8111/intent `
  -H "Content-Type: application/json" `
  -d '{"query": "analyze the risk factors"}' | python -m json.tool
# → {"agent": "forge", "confidence": 0.87, "latency_ms": 10}
```

### NPU routing hierarchy

- `POST /embed` → MiniLM-L6-v2 (384-dim) primary, BGE-large ONNX fallback
- `POST /embed_query` → single text variant
- `POST /transcribe` → whisper-base, lazy-loaded, any audio format
- `POST /intent` → cosine similarity to mean-prototype embeddings, ~10ms

---

## Pipeline Backend

**Port**: 8099  
**File**: `sovereignnation/pipeline_backend.py`

```powershell
# Test intent routing wrapper
curl -s -X POST http://localhost:8099/route `
  -H "Content-Type: application/json" `
  -d '{"query": "review this code for bugs"}' | python -m json.tool
# → {"agent": "codex", "confidence": 0.91}

# Test auto-routed chat (embeds last user message → injects agent system prompt)
curl -s -X POST http://localhost:8099/chat `
  -H "Content-Type: application/json" `
  -d '{"messages": [{"role": "user", "content": "analyze revenue trends"}], "auto_route": true}' | python -m json.tool
# → {"reply": "...", "routed_to": "oracle"}
```

---

## Demo Mode

```batch
REM Enable demo mode (pauses learner + amplifier, no key needed for serve.py)
C:\Users\leer4\GH05T3\DEMO_ON.bat

REM Disable demo mode
C:\Users\leer4\GH05T3\DEMO_OFF.bat
```

Demo mode creates `data/demo_mode.flag`. `serve.py` checks for this file and bypasses API key requirements. The demo model (`gh05t3:latest`) stays loaded in VRAM from KAIROS inference cycles — no cold start during demos.

Demo flow: LinkedIn DM → `demo_video.html` link → email reply → close  
Demo video: `C:\Users\leer4\Documents\demo_video.html` (animated HTML, subtitles, no voice — never use Loom)

---

## Full Test Suite

```powershell
cd C:\Users\leer4\GH05T3
python -m pytest -q
# Expected: 291 passed, 15 skipped, 0 failures (~3m 51s)
```

No env prefix needed — `conftest.py` at repo root sets `AETHYRO_SKIP_LICENSE=1` and `GH05T3_TEST_MODE=1` automatically.

### Live integration tests (requires stack running)

```powershell
$env:REACT_APP_BACKEND_URL = "http://localhost:8002"
python -m pytest tests/test_gh05t3.py tests/test_gh05t3_phase2.py tests/test_gh05t3_phase3.py tests/test_gh05t3_phase4.py tests/test_swarm.py -v
```

### WSL integration tests (requires WSL services)

```powershell
$env:WSL_SERVICES_UP = "1"
python -m pytest tests/test_wsl_integration.py -v
```

See `test-gh05t3` skill for full test reference.

---

## Health Check Sequence (verify complete stack)

Run in order — each layer depends on the previous:

```powershell
# 1. Ollama
Write-Host "Ollama:" (Invoke-RestMethod http://localhost:11434/api/tags).models.Count "models loaded"

# 2. NPU embed service
Write-Host "NPU:" (Invoke-RestMethod http://localhost:8111/health).status

# 3. Backend
Write-Host "Backend:" (Invoke-RestMethod http://localhost:8001/health).status

# 4. Gateway
Write-Host "Gateway:" (Invoke-RestMethod http://localhost:8002/health).status

# 5. Pipeline backend
Write-Host "Pipeline:" (Invoke-RestMethod http://localhost:8099/health).status

# 6. Economy API
Write-Host "Economy:" (Invoke-RestMethod http://localhost:8081/health).status

# 7. Supervisor (all services)
$status = Invoke-RestMethod http://localhost:8090/status
Write-Host "Supervisor: all_ok=$($status.all_ok) services=$($status.services.Count)"
```

All should return in < 2 seconds each. If any times out: check the logs below.

---

## Log Locations

```powershell
# Supervisor logs
Get-Content C:\Users\leer4\GH05T3\logs\supervisor.log -Tail 50

# Backend logs
Get-Content C:\Users\leer4\GH05T3\logs\backend.log -Tail 50

# Gateway logs
Get-Content C:\Users\leer4\GH05T3\logs\gateway.log -Tail 50

# NPU embed service
Get-Content C:\Users\leer4\GH05T3\logs\npu_embed.log -Tail 50
```

---

## SovereignCore Integration

SovereignCore runs in WSL at port :9000 and is aggregated into the supervisor health check:

```bash
# WSL
cd /home/leer4/sovereign-core && ./scripts/start.sh
```

```powershell
# Verify from Windows (WSL auto-forwards :9000 to Windows localhost)
Invoke-RestMethod http://localhost:9000/v1/agents
```

The supervisor at :8090 shows `:9000` health alongside `:8002` in its aggregated status.

---

## Common Startup Failures

### Supervisor won't start (port 8090 in use)
```powershell
KILL_PORTS.bat   # kills 8001/8002/8081/8090/8099
START_ALL.bat    # restart
```

### Backend fails: "ModuleNotFoundError"
The venv at `backend/` isn't activated. `START_ALL.bat` handles this via the conda/venv activation in its script — if running manually:
```powershell
cd C:\Users\leer4\GH05T3
.\.venv\Scripts\activate
python backend\server.py
```

### NPU service won't start
```powershell
# Must use ryzen-ai conda env
conda activate ryzen-ai-1.7.0
python sovereignnation\npu_embedding_service.py
# If ryzen-ai env missing: conda env create --file environment.yml --prefix C:\Users\leer4\.conda\envs\ryzen-ai-1.7.0
```

### Ollama shows CPU-only (no GPU)
1. Check LM Studio is closed
2. Check RTX Remix is closed
3. Verify `cuda_v13/ggml-cuda.dll` exists
4. Check Ollama version is 0.23.2 (not auto-updated)
5. Restart Ollama tray app

### "gateway_v3 license gate" during startup
```powershell
$env:AETHYRO_SKIP_LICENSE = "1"
# Or set permanently in system env vars via Windows Settings → Environment Variables
```
