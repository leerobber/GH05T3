# GH05T3 — Claude Session Memory
> READ THIS FIRST. Test every fix before presenting it.

## Project layout
```
GH05T3/
  backend/          FastAPI servers + all Python modules
    server.py       existing backend — port 8001, requires MongoDB
    gateway_v3.py   v3 SwarmBus gateway — port 8002, no MongoDB needed
    swarm/          SwarmBus + 5 specialist agents (v3)
    integrations/   Claude API + GitHub automation (v3)
    core/           config.py, omega_loop.py
    evolution/      kairos.py, sage.py
    memory/         memory_palace.py (SQLite)
    security/       ghost_protocol.py
    swarm_legacy.py old SA³ swarm (renamed to avoid package conflict)
    requirements.txt
    start_v3.sh     Linux/Mac launcher for gateway_v3
  frontend/
    src/
      App.js
      components/ghost/
        SwarmBusPanel.jsx   v3 live bus panel (stream/agents/github/claude/keys tabs)
        V3SecretsModal.jsx  auto-popup keys entry on first boot
      lib/ghostApi.js       gw3* functions point at REACT_APP_GW3_URL
  native/windows/
    install.ps1     one-time setup — installs in-place in repo root
    run.bat         starts all 5 processes
  INTEGRATIONS.md   Tier 1/2/3 roadmap
  .env.example      template
```

## Port map (no conflicts)
| Port | Process |
|------|---------|
| 27017 | MongoDB |
| 8001  | server.py (existing FastAPI + Mongo) |
| 8002  | gateway_v3 (SwarmBus · Claude · GitHub) |
| 8010  | vLLM primary (RTX 5050, fill when ready) |
| 8011  | llama.cpp verifier (Radeon 780M) |
| 8012  | llama.cpp fallback (CPU) |
| 3210  | frontend static bundle |

## Known issues / gotchas — NEVER repeat these mistakes

### 1. requirements.txt had broken editable install
`-e /tmp/recon/sovereign-core` — was a CI artifact, not a real package.
**Fixed:** removed. Nothing in the codebase imports it.

### 2. install.ps1 self-copy error
Windows filesystem is case-insensitive. `$env:USERPROFILE\gh05t3` and
`$env:USERPROFILE\GH05T3` (the cloned repo) resolve to the same path.
Copy-Item fails with "cannot overwrite item with itself".
**Fixed:** install.ps1 now derives `$APP` from `$MyInvocation` (the repo
root itself) — installs in-place, no copy step.

### 3. swarm.py vs swarm/ package conflict
Original `backend/swarm.py` (old SA³) conflicts with new `backend/swarm/`
package. Python resolves the package directory over the module file.
**Fixed:** renamed to `swarm_legacy.py`; server.py + swarm_tasks.py import
from `swarm_legacy`.

### 4. gateway_v3 port collision
gateway_v3 must NOT use port 8001 — that's server.py's port.
Default in core/config.py and start_v3.sh is **8002**.

### 5. REACT_APP_GW3_URL must be set before yarn build
CRA/craco bakes REACT_APP_* at build time, not runtime.
install.ps1 writes `frontend/.env.local` before `yarn build`.

### 6. Test before presenting fixes
Always run `python -m py_compile <file>` for Python.
Always verify path logic before writing PowerShell install scripts.
When editing install scripts: trace every variable, especially on
Windows where paths are case-insensitive.

## Active branch
`claude/new-session-GYmE5` — all v3 work lives here.

## Keys setup flow
1. `.\install.ps1` (one time, from `native\windows\`, as Administrator)
2. `.\run.bat` (from repo root — copied there by install.ps1)
3. Open `http://localhost:3210` — V3SecretsModal pops up automatically
4. Paste Anthropic key (`sk-ant-...`) + GitHub PAT (`ghp_...`) → save
5. Keys written to `backend/.env`, hot-loaded — no restart needed
