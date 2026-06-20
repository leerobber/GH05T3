# GH05T3

> Self-improving local AI super-agent. Multi-GPU mesh, sovereign by default, zero-egress when you want it that way.

GH05T3 is the engine; **Avery** is the humanized brand persona on top. The system wires a fine-tuned LoRA inference server, a multi-provider LLM router (gh05t3 → ollama → groq → google → anthropic), a FastAPI gateway, a SwarmBus of specialist agents, and a React/Vite dashboard into one launcher.

---

## Port map

| Port  | Process                                           |
|-------|---------------------------------------------------|
| 27017 | MongoDB                                           |
| 8001  | `backend/server.py` (FastAPI + Mongo)             |
| 8002  | `backend/gateway_v3.py` (SwarmBus · Claude · GitHub · Stripe · Story Editor) |
| 8010  | `backend/gh05t3_inference.py` (LoRA model server) |
| 8011  | llama.cpp verifier (Radeon 780M)                  |
| 8012  | llama.cpp fallback (CPU)                          |
| 3210  | Frontend static bundle                            |

---

## Quick start (Windows / TatorTot)

```bash
# 1. One-time setup (Administrator PowerShell)
cd native\windows
.\install.ps1

# 2. Train the LoRA adapter on local GPU (~30-45 min first run)
.\train.bat

# 3. Boot everything
cd ..\..
.\run.bat
```

Open `http://localhost:3210`. The V3SecretsModal pops up on first boot — paste your Anthropic key and GitHub PAT.

## Quick start (Linux / dev)

```bash
# Backend
cd backend
pip install -r requirements.txt
AETHYRO_SKIP_LICENSE=1 uvicorn server:app --host 0.0.0.0 --port 8001 &
AETHYRO_SKIP_LICENSE=1 uvicorn gateway_v3:app --host 0.0.0.0 --port 8002 &

# Frontend
cd ../frontend
yarn install
REACT_APP_GW3_URL=http://localhost:8002 yarn build
yarn preview
```

---

## Environment

Copy `.env.example` to `backend/.env` and fill in the keys you actually need. Everything is optional — the gateway degrades gracefully when a provider is absent.

Required env to actually run anything: **none.** Optional but useful:

- `ANTHROPIC_API_KEY` — Claude fallback in the LLM router
- `GITHUB_PAT` — repo automation, webhook fan-out
- `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET` — subscriber billing
- `HF_TOKEN` — push trained adapters to HuggingFace
- `RUNPOD_API_KEY` — remote training pods
- `LLM_PROVIDER=gh05t3` — switch to the local fine-tuned model (requires an adapter in `backend/models/gh05t3_lora_adapter/`)
- `AETHYRO_SKIP_LICENSE=1` — skip the license gate (CI / dev)

See `.env.example` for the full list with inline docs.

---

## Repo layout

```
GH05T3/
├── oss/                    Canonical OSS layer — import as `oss.*` (tests + gateway mount)
│   ├── api/router.py       FastAPI routes mounted at /oss by gateway_v3
│   ├── forge/              Adapter routing, MoE farm, lab inference
│   ├── lab/                SaaS product lab, metrics, trading strategy
│   ├── kernel/             Civilization kernel FSM + orchestrator
│   ├── substrate/          Genomic substrate reset hooks
│   ├── dna/ · mind/ · train/ · ecosystem/ · world/ …
├── backend/                FastAPI app, gateway, swarm, integrations, training
│   ├── server.py           Port 8001 — main app, requires MongoDB
│   ├── gateway_v3.py       Port 8002 — SwarmBus / Claude / GitHub / Stripe
│   ├── gh05t3_inference.py Port 8010 — OpenAI-compatible LoRA inference
│   ├── ghost_llm.py        Multi-provider router (gh05t3 → ollama → groq → google → anthropic)
│   ├── oss/                MVS runtime engine only (loop, mvs, genomic_substrate, theory lab)
│   ├── swarm/              SwarmBus + 5 specialist agents
│   ├── integrations/       Claude, GitHub, Stripe, story editor
│   ├── training/           train_local.py (canonical path), datasets
│   └── tests/              pytest suite
├── frontend/               React 19 + Vite 8 + Tailwind 3, port 3000 (dev) / 3210 (preview)
│   └── src/components/ghost/   All UI panels
├── deploy/                 Vercel, Cloudflare Pages, tunnel configs
├── kairos/                 KAIROS framework — Kickoff/Align/Implement/Refine/Optimize/Scale
├── swarm/                  Top-level swarm bus + agents
├── sovereignnation/        SovereignNation product surface (gates, pipeline, phi service)
├── scripts/                Training, runtime, and utility scripts
│   ├── training/           Training pipelines (Avery, Sovereign, RunPod, Kairos gen, data_gen)
│   └── runtime/            Ops scripts + standalone agents
│       ├── bridge/         Multi-provider LLM mesh (Claude, Gemini, NVIDIA roles)
│       └── companion/      Standalone local companion agent (own requirements.txt)
├── native/                 Platform-specific launchers
│   ├── windows/            install.ps1, train.bat, run.bat, .ps1, .bat
│   └── android/            termux_setup.sh
├── tests/                  Top-level pytest suite (imports `oss.*`, not `backend.oss.*`)
├── memory/                 SQLite memory palace, deploy checklist, PRD
├── CLAUDE.md               Session memory — read first if hacking on training
├── INTEGRATIONS.md         Tier 1/2/3 integration roadmap
└── .env.example            Full environment template with docs
```

**Import rule:** Tests and `gateway_v3` use top-level `oss.*`. `backend/oss/` holds the MVS simulation engine (`loop.py`, `mvs.py`, `genomic_substrate.py`, theory lab). Do not duplicate `oss/forge`, `oss/api`, or `oss/lab` under `backend/oss/`.

---

## Training

**Canonical path: `native\windows\train.bat` on a local CUDA box.**

Kaggle was abandoned — see CLAUDE.md for the gory details. The two non-negotiable rules:

1. Do **not** cast LoRA adapters to fp16 after `get_peft_model()`. PEFT keeps adapters fp32 on purpose.
2. Always set `gradient_checkpointing_kwargs={"use_reentrant": False}` in `TrainingArguments`.

Both rules are baked into `backend/training/train_local.py`. Don't undo them.

---

## CI

GitHub Actions runs on every push to `main` and every PR:

- **Backend job** — Python 3.12, installs `backend/requirements-ci.txt`, runs `py_compile` smoke tests on the training scripts, then `pytest tests/` in both root and backend with `AETHYRO_SKIP_LICENSE=1`.
- **Frontend job** — Node 20, `yarn install --frozen-lockfile`, `yarn build` against `REACT_APP_GW3_URL=http://localhost:8002`.

Live-server tests are auto-skipped (`-m "not live and not integration"`).

> **Python 3.12 is required** — `kairos/kairos.py` and a few other modules use syntax that 3.11 rejects.

---

## License

Aethyro license gate runs at import in `backend/server.py`. Set `AETHYRO_SKIP_LICENSE=1` to bypass it for development and CI.

---

## Contributing

1. Branch from `main`.
2. Run `pytest tests/ backend/tests/ -v` locally with `AETHYRO_SKIP_LICENSE=1`.
3. For frontend changes: `cd frontend && yarn build` must succeed clean.
4. PRs go through the CI in `.github/workflows/ci.yml`.
