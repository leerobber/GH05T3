# GH05T3 — Claude Session Memory
> READ THIS FIRST. Test every fix before presenting it.

## Project layout
```
GH05T3/
  backend/
    server.py             existing backend — port 8001, requires MongoDB
    gateway_v3.py         v3 SwarmBus gateway — port 8002, no MongoDB needed
    gh05t3_inference.py   LoRA inference server — port 8010, OpenAI-compatible
    ghost_llm.py          multi-provider LLM router (gh05t3 > ollama > groq > google > anthropic)
    personas.py           Avery + agent team personas (Iris/ORACLE, Marcus/FORGE, etc.)
    swarm/                SwarmBus + 5 specialist agents (v3)
    integrations/
      claude_integration.py
      github_integration.py
      stripe_integration.py   Stripe webhooks + subscriber store (data/subscribers.json)
      story_editor.py         Stateful developmental story editor (11-step intake)
    prompts/
      story_editor.md         Full story editor system prompt (verbatim)
    core/                 config.py, omega_loop.py
    evolution/            kairos.py, sage.py
    memory/               memory_palace.py (SQLite)
    security/             ghost_protocol.py
    models/
      gh05t3_lora_adapter/    Fine-tuned adapter — produced by train_local.py
    training/
      train_local.py               LOCAL training script — use this, not Kaggle
      gh05t3_finetune_2xT4.ipynb   Kaggle notebook (archived, do not rely on)
    swarm_legacy.py       old SA³ swarm (renamed to avoid package conflict)
  frontend/
    src/
      App.js
      components/ghost/
        SwarmBusPanel.jsx   v3 live bus panel
        V3SecretsModal.jsx  auto-popup keys entry on first boot
      lib/ghostApi.js       gw3* functions point at REACT_APP_GW3_URL
  native/
    windows/
      install.ps1     one-time setup
      train.bat       local training launcher (runs train_local.py)
    android/
      termux_setup.sh   Termux/Android node setup (Claude Code pinned v2.1.112)
  INTEGRATIONS.md   Tier 1/2/3 roadmap
  .env.example      template
```

## Port map (no conflicts)
| Port | Process |
|------|---------|
| 27017 | MongoDB |
| 8001  | server.py (existing FastAPI + Mongo) |
| 8002  | gateway_v3 (SwarmBus · Claude · GitHub · Stripe · Story Editor) |
| 8010  | gh05t3_inference.py (LoRA model server — starts with run.bat) |
| 8011  | llama.cpp verifier (Radeon 780M) |
| 8012  | llama.cpp fallback (CPU) |
| 3210  | frontend static bundle |

## Hardware (TatorTot — user's desktop)
- Lenovo LOQ 15, Windows
- NVIDIA RTX 5050 dGPU → port 8010 (gh05t3_inference.py)
- AMD Radeon 780M iGPU → port 8011
- Ryzen 7 CPU → port 8012
- Tailscale: 100.94.227.81 (hostname: tail1457e2.ts.net)
- SSH user: leer4

## Mobile node (TIA — Android Termux)
- Termux on Android (aarch64)
- Claude Code pinned to v2.1.112 (last Termux-compatible)
- Run `native/android/termux_setup.sh` once to configure
- SSH alias `tator-gh05t3` → TatorTot tmux session
- Ollama models locally: cogito:latest, llama3.2:3b

## Avery / startup context
- **Avery** is the humanized brand persona for the startup
- **GH05T3** is the engine underneath
- Agent team = AI employees until real hires:
  - Avery (GH05T3) — Founder & Chief Intelligence
  - Iris Chen (ORACLE) — Chief Research Officer
  - Marcus Reid (FORGE) — CTO
  - Zoe Nakamura (CODEX) — VP Engineering
  - Viktor Steele (SENTINEL) — CSO
  - Kai Okafor (NEXUS) — COO
- Stripe: live key linked to Substack. Webhook endpoint: /stripe/webhook
  - Env vars needed: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET

## Training — LOCAL ONLY (Kaggle abandoned)
Kaggle repeatedly failed: gradient collapse every run despite fp16 fixes (session env unpredictable).
**Canonical training path: `native\windows\train.bat` on TatorTot's RTX 5050.**

- Model: Qwen/Qwen2.5-Coder-3B-Instruct + LoRA rank 16, 7324 examples, 500 steps
- Script: `backend/training/train_local.py`
- Launcher: `native\windows\train.bat` (auto-installs deps on first run)
- Output: `backend/models/gh05t3_lora_adapter/`
- Requires: PyTorch 2.6+cu128 (RTX 5050 is Blackwell sm_120)

### Critical training fixes (all baked into train_local.py)
1. Cast LoRA adapters to fp16 after `get_peft_model()` — PEFT inits fp32, causes NaN at step 10
2. `gradient_checkpointing_kwargs={"use_reentrant": False}` — reentrant mode + fp16 + hooks → NaN gradients
3. `fp16=True`, `lr=2e-5`, `max_grad_norm=0.3`

### After training
```
# backend/.env
LLM_PROVIDER=gh05t3
```
Then `run.bat` — gh05t3_inference.py loads the adapter on port 8010.

## Active branch
`claude/fix-multi-gpu-training-2WHKH` — all current work lives here.

## API endpoints added (gateway_v3.py, port 8002)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /avery | GET | Avery's public identity card |
| /avery/team | GET | Full agent roster |
| /avery/story/start/{id} | GET | Open story editor session |
| /avery/story/turn | POST | Send message to story editor |
| /avery/story/sessions | GET | List sessions |
| /stripe/webhook | POST | Stripe event receiver |
| /stripe/subscribers | GET | Subscriber counts |

## Known issues / gotchas — NEVER repeat these mistakes

### 1. requirements.txt broken editable install
`-e /tmp/recon/sovereign-core` — CI artifact, not a real package.
**Fixed:** removed.

### 2. install.ps1 self-copy error
Windows case-insensitive paths. `$env:USERPROFILE\gh05t3` == `$env:USERPROFILE\GH05T3`.
**Fixed:** install.ps1 derives `$APP` from `$MyInvocation`, installs in-place.

### 3. swarm.py vs swarm/ package conflict
**Fixed:** renamed to `swarm_legacy.py`.

### 4. gateway_v3 port collision
Must use 8002, NOT 8001.

### 5. REACT_APP_GW3_URL must be set before yarn build
CRA bakes env vars at build time.

### 6. LoRA training collapse (CRITICAL — do not revert)
PEFT fp32 adapter + fp16 base model → loss explosion at step 10 (266), then 0.0 forever.
Two compounding causes:
- PEFT inits adapters fp32; fp16=True GradScaler sees NaN → permanently skips updates
- `gradient_checkpointing` with `use_reentrant=True` (default) reruns forward with fp16 → NaN gradients
**Fix (both required):** cast adapters to fp16 after get_peft_model() + `gradient_checkpointing_kwargs={"use_reentrant": False}`
Both fixes are in `train_local.py`. Do NOT remove either.

### 7. Kaggle abandoned
Kaggle env is unpredictable (Python 3.12 + mismatched CUDA, token issues, GPU resets every push).
All training is now local via `native\windows\train.bat`. Do not suggest Kaggle.

### 8. RTX 5050 requires PyTorch 2.6+cu128
Blackwell (sm_120) is not supported in PyTorch < 2.6. Training will silently fail or produce garbage.
Install: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128`

### 9. Test before presenting fixes
Always run `python -m py_compile <file>` for Python.
Always validate notebook JSON: `python3 -c "import json; json.load(open('notebook.ipynb'))"`

## Keys setup flow
1. `.\install.ps1` (one time, from `native\windows\`, as Administrator)
2. `native\windows\train.bat` — trains LoRA adapter on RTX 5050 (~30-45 min first run)
3. `.\run.bat` (from repo root — starts MongoDB, backend, gateway, gh05t3_inference, frontend)
4. Open `http://localhost:3210` — V3SecretsModal pops up automatically
5. Paste Anthropic key (`sk-ant-...`) + GitHub PAT (`ghp_...`) → save
6. Keys written to `backend/.env`, hot-loaded — no restart needed
7. Set STRIPE_SECRET_KEY + STRIPE_WEBHOOK_SECRET in backend/.env for billing
8. Set LLM_PROVIDER=gh05t3 in backend/.env to use the fine-tuned model
