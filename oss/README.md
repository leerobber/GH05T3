# Sovereign Operations Stack

**Version 0.1.0 · Phase 1 Foundation**

The Sovereign Operations Stack (OSS) is the specification and contract layer for GH05T3. It defines how agents are modeled, how work is routed through the swarm, how credits move, and how the platform exposes a single API surface—without replacing the operational runtime in `backend/`.

Think of OSS as the blueprint; `backend/` is the engine room. New platform behavior should land in OSS first as schemas and facades, then delegate to existing modules until migration is complete.

For architecture, layer maturity, and roadmap detail, see **[BLUEPRINT.md](./BLUEPRINT.md)**.

---

## Design principle

OSS follows a **hybrid integration model**:

| Layer | Role |
|-------|------|
| `oss/schemas/` | Canonical data contracts (genomes, tasks, ledger events) |
| `oss/adapters/` | Bridges into `backend/` — no duplicated business logic |
| `oss/api/` | Public HTTP surface mounted at `/oss` on gateway `:8002` |
| `backend/` | Persistence, inference, SwarmBus, evolution, billing — unchanged spine |

Do not fork `gateway_v3.py`, `swarm/`, or `evolution/` into OSS. Extend through adapters.

---

## Professional naming map

Documentation and external communication use the names in the left column. Source code retains established module paths for stability.

| Professional term | Code / module path |
|-------------------|-------------------|
| Genome Layer | `oss/dna/`, `oss/schemas/genome.py` |
| Orchestration Layer | `oss/mind/` |
| Credit Layer (Platform Credits, **NC**) | `oss/economy/neuro_coin.py` |
| Performance Incentive Model | `oss/economy/desire.py` |
| Protocol Adapters | `oss/adapters/` |
| Adaptive Learning Pipeline | `oss/adapters/evolution.py` → `backend/evolution/` |
| Gateway Surface | `oss/api/router.py` → `backend/gateway_v3.py` |

---

## Repository layout

```
oss/
  README.md                 ← you are here
  BLUEPRINT.md              ← architecture & phase roadmap
  schemas/
    genome.py               Trait, GenomeRecord, SwarmTask, SwarmResult
  dna/
    omni_dna.py             Evolvable agent genome model
    store.py                SQLite persistence (specialist seeds)
    omega_rewrite.py        High-score configuration patch manifests
  mind/
    omni_mind.py            Trait-gated collective orchestration
    collective.py           Shared operational state across agents
    selector.py             Task-to-agent matching
    holographic.py          XOR shard memory (Phase 2+)
  economy/
    neuro_coin.py           Platform Credits over ledger + marketplace
    desire.py               Performance incentive scoring
  adapters/
    swarm.py                SwarmBus + agent invocation
    evolution.py            KAIROS cycle recording
    marketplace.py          Job queue delegation
  api/
    router.py               FastAPI routes
  cli/
    demo_swarm.py           Foundation milestone demonstration
  data/
    genomes.db              Runtime genome store (gitignored)
```

---

## Requirements

- Python 3.12 with `backend/.venv` activated
- GH05T3 gateway running on port **8002** (via `run.bat` or `run_stack.py`)
- Optional: Ollama or configured cloud inference for live swarm solves

---

## Quick start

### 1. Verify the stack

```bat
run.bat --review
curl http://localhost:8002/oss/health
```

Expected: `{"status":"ok","layer":"oss","version":"0.1.0"}`

### 2. Seed specialist genomes

```bat
backend\.venv\Scripts\python.exe oss\cli\demo_swarm.py --seed-only
```

Loads six registry-aligned specialists (GH05T3, ORACLE, FORGE, CODEX, SENTINEL, NEXUS) into `oss/data/genomes.db`.

### 3. Run a collective solve

```bat
backend\.venv\Scripts\python.exe oss\cli\demo_swarm.py ^
  --problem "Reduce gateway latency on port 8002 without weakening authentication" ^
  --traits coding self_reflection ^
  --max-agents 3
```

### 4. Exercise the HTTP API

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/oss/health` | Layer status |
| `GET` | `/oss/agents` | Active genome roster + collective state |
| `GET` | `/oss/agents/{genome_id}` | Single genome record |
| `POST` | `/oss/agents/{genome_id}/evolve` | Apply trait deltas from performance score |
| `GET` | `/oss/mind/state` | Shared orchestration state |
| `POST` | `/oss/swarm/solve` | Trait-gated collective task execution |
| `GET` | `/oss/economy/stats` | Platform Credits + pending job count |
| `POST` | `/oss/economy/delegate` | Post marketplace sub-job with NC reward |

Example:

```bash
curl -X POST http://localhost:8002/oss/swarm/solve \
  -H "Content-Type: application/json" \
  -d '{"problem":"Audit Stripe webhook idempotency","required_traits":["security"],"max_agents":2}'
```

---

## GHOST DECK integration

From the repository root:

```bat
python ghostdeck.py swarm "reduce latency" --mock
python ghostdeck.py delegate --task "security scan" --agent SENTINEL --reward 50
python ghostdeck.py genomes
```

---

## Test suite

Always run through the backend virtual environment:

```bat
backend\.venv\Scripts\python.exe -m pytest tests\test_oss_dna.py tests\test_oss_mind_swarm.py tests\test_oss_economy.py tests\test_oss_tier2.py -v
```

Sixteen tests cover genome persistence, swarm selection, Platform Credits, omega patch manifests, incentive scoring, and holographic shards.

---

## Relationship to GH05T3 modules

OSS does not replace these—it wraps them:

| Capability | Backend module |
|------------|----------------|
| Agent manifests | `backend/agent_registry.py` |
| Dynamic invocation | `backend/agent_forge.py` |
| Specialist personas | `backend/personas.py` |
| Message bus | `backend/swarm/bus.py` |
| Specialist roster | `backend/swarm/agents.py` |
| Local credits | `backend/economy/ledger.py` |
| Job marketplace | `backend/agent_marketplace.py` |
| Evolution cycles | `backend/evolution/kairos.py`, `sage.py`, `map_elites.py` |
| API gateway | `backend/gateway_v3.py` |
| Commerce | `backend/integrations/stripe_integration.py` |

---

## Phase status (summary)

| Phase | Focus | Status |
|-------|-------|--------|
| **1 — Foundation** | Genomes, orchestration, credits, gateway API | **In progress** — core paths operational |
| **2 — Unification** | Registry sync, mesh contract, memory facade, external ledger bridge | Planned |
| **3 — Advanced** | Configuration patches, incentive model production use, holographic memory | Scaffolded |

Full maturity assessment and gap analysis: **[BLUEPRINT.md](./BLUEPRINT.md)**.

---

## Conventions for contributors

1. **New contracts** → `oss/schemas/` first, then adapter.
2. **New HTTP routes** → `oss/api/router.py`; mount stays in `gateway_v3.py`.
3. **No direct edits** to swarm or evolution core unless fixing a runtime bug.
4. **Runtime databases** under `oss/data/` are local artifacts—never commit.
5. **Voice, avatar, and TTS** are out of scope unless explicitly requested.

---

## Ports (reference)

| Port | Service |
|------|---------|
| 8002 | Gateway v3 + `/oss/*` |
| 8001 | Backend API (`server.py`) |
| 3210 | Dashboard (`frontend/build`) |
| 8010 | Fine-tuned inference (optional) |
| 8081 | External sovereign economy API (bridge pending) |
| 8105 | GHOST DECK bus |

---

*GH05T3 · Aethyro · Sovereign Operations Stack*