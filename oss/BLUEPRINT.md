# Sovereign Operations Stack — Architecture Blueprint

**Document class:** Platform architecture · Phase 1 Foundation  
**Audience:** Engineering, product, operations  
**Status:** Living document — revised as layers mature

---

## Executive summary

GH05T3 already runs a capable agent platform: registry-backed manifests, a live SwarmBus, dual memory substrates, a KAIROS → SAGE → MAP-Elites evolution loop, marketplace job queues, Stripe commerce hooks, and a gateway with a production dashboard. What it lacks is a **single contract** that ties those pieces together under one vocabulary, one credit model, and one discovery surface.

The Sovereign Operations Stack (OSS) supplies that contract. It is not a rewrite. It is a thin, deliberate layer—schemas, facades, and routes—that sits above `backend/` and absorbs complexity over time without destabilizing what already ships.

At Phase 1 maturity, OSS is fit for **foundation work**: demonstration swarms, genome persistence, Platform Credit accounting, and API exposure. It is not yet fit for production-grade multi-tenant isolation, full mesh convergence, or a unified external economy bridge. That honesty is intentional; the blueprint names what exists, what is partial, and what comes next.

---

## 1. Architectural stance

### 1.1 The hybrid model

Three approaches were considered. Only one scales with GH05T3's operational reality.

| Approach | Verdict |
|----------|---------|
| OSS-only rewrite | Rejected — breaks `supervisor.py`, `run.bat`, import graphs, and years of hardened runtime code |
| Backend-only extension | Rejected — perpetuates naming drift (Aethyro / GH05T3 / SovereignNation) and buries contracts |
| **Hybrid: OSS contracts + backend runtime** | **Adopted** — blueprint clarity without forklift migration |

OSS owns **what things mean**. Backend owns **how things run**.

### 1.2 Layered platform model

The stack is organized into nine logical layers. Each maps to existing GH05T3 modules today and to OSS packages as contracts harden.

```
┌─────────────────────────────────────────────────────────────────┐
│  Gateway Layer          frontend · gateway_v3 · tunnels · MCP   │
├─────────────────────────────────────────────────────────────────┤
│  Commerce Layer         Stripe · subscriptions · license gate   │
├─────────────────────────────────────────────────────────────────┤
│  Evolution Layer        KAIROS · SAGE · MAP-Elites · omega      │
├─────────────────────────────────────────────────────────────────┤
│  Protocol Layer         SwarmBus · GhostScript · MCP messages   │
├─────────────────────────────────────────────────────────────────┤
│  Orchestration Layer    trait-gated swarm · collective state    │
├─────────────────────────────────────────────────────────────────┤
│  Genome Layer           traits · lineage · registry alignment   │
├─────────────────────────────────────────────────────────────────┤
│  Credit Layer           Platform Credits · jobs · ledger bridge │
├─────────────────────────────────────────────────────────────────┤
│  Mesh Layer             peers · Tailscale · discovery           │
├─────────────────────────────────────────────────────────────────┤
│  Environment Layer      worlds · simulations (Phase 2+)         │
└─────────────────────────────────────────────────────────────────┘
                              │
                    backend/ runtime spine
```

---

## 2. Layer inventory

### 2.1 Genome Layer

**Purpose.** Every agent on the platform should have a versioned identity: measurable traits, generational lineage, and a stable link to its registry manifest. Personas and SQLite registry rows are necessary but not sufficient—they describe *who* runs, not *how capability evolves*.

**OSS implementation.**

- `oss/schemas/genome.py` — `Trait`, `GenomeRecord`, trait typing enum
- `oss/dna/omni_dna.py` — evolvable genome with score-driven mutation
- `oss/dna/store.py` — SQLite store seeded with six specialists
- `oss/dna/omega_rewrite.py` — configuration patch manifests for high-performing genomes (score ≥ 0.85)

**Backend dependencies.**

- `backend/agent_registry.py` — manifest source of truth
- `backend/agent_forge.py` — runtime invocation
- `backend/personas.py` — display identity and system prompts
- `backend/training_data/agent_training/*.jsonl` — training corpora per role

**Maturity: Partial.** Genomes persist and evolve in isolation. Registry manifests are not yet automatically synchronized into genome records on boot. Trait schema versioning and crossover are defined in code but not exposed as a public contract.

**Next unification step.** `oss/adapters/registry.py` — bidirectional sync between `agent_registry.db` slugs and `genomes.db` records.

---

### 2.2 Orchestration Layer

**Purpose.** Route work to the right specialists under explicit constraints—required traits, agent caps, bus visibility—then synthesize outcomes and feed performance back into evolution.

**OSS implementation.**

- `oss/mind/omni_mind.py` — bootstrap, task assignment, collective solve
- `oss/mind/selector.py` — trait-weighted agent selection
- `oss/mind/collective.py` — shared operational state (aggregated trait intensity, task memory index)
- `oss/mind/holographic.py` — XOR shard storage (Phase 2+ scaffold)

**Backend dependencies.**

- `backend/swarm/bus.py` — channels, JSONL log, WebSocket relay
- `backend/swarm/agents.py` — ORACLE, FORGE, CODEX, SENTINEL, NEXUS, CHRONICLE
- `backend/core/omega_loop.py` — platform loop integration
- `backend/autotelic.py` — goal-driven behavior
- `backend/gh05t3_state.py` — hardware and topology narrative

**Maturity: Operational for Phase 1.** `POST /oss/swarm/solve` executes trait-gated selection, parallel invocation via adapters, synthesis, and KAIROS cycle recording. Collective state is a deliberate stub—shared memory and aggregated trait vectors, not full consensus protocols.

**Gap.** No global mind abstraction beyond bus channels and collective snapshot. Acceptable for Foundation; consensus and conflict resolution belong in Phase 2.

---

### 2.3 Credit Layer

**Purpose.** One currency semantics for rewarding agent work, posting jobs, and eventually bridging to the external sovereign economy service.

**OSS implementation.**

- `oss/economy/neuro_coin.py` — **Platform Credits (NC)** over `backend/economy/ledger.py`
- `oss/economy/desire.py` — **Performance Incentive Model** — loyalty scoring from fulfilled objectives
- `oss/adapters/marketplace.py` — job posting into `backend/agent_marketplace.py`

**Backend dependencies.**

- `backend/economy/ledger.py` — local credit balances
- `backend/economy/economy_bridge.py` — training → credits
- `backend/agent_marketplace.py` — SQLite jobs, autoscale workers
- `backend/sovereign_economy.py` — in-repo client helpers
- External `agent-economy` on `:8081` (supervisor-managed, outside this repository)

**Maturity: Partial.** NC unifies ledger and marketplace posting inside GH05T3. Three economic surfaces still coexist:

1. Local ledger (NC)
2. Marketplace job rewards
3. External economy API on port 8081

**Next unification step.** `oss/adapters/sovereign.py` — read-through and settlement bridge to `:8081` without merging codebases.

---

### 2.4 Mesh Layer

**Purpose.** A single peer discovery and health contract across Tailscale, GitHub relay, FRONTIER bus, and legacy mesh loops.

**Backend dependencies (today).**

- `backend/peer_mesh.py`
- `backend/swarm/peer_registry.py`
- `backend/tailscale_manager.py`
- `bridge/mesh_loop.py`
- `frontier/ghostdeck_bus.py` (port 8105)
- `docs/superpowers/plans/2026-05-21-mesh-convergence.md`

**OSS status: Not yet packaged.** Mesh convergence remains open engineering work. Phase 2 deliverable: `oss/grid/mesh.py` as canonical `/peers` schema and health semantics.

**Maturity: Fragmented.** Functional for LAN and Tailscale access; not formally contracted in OSS.

---

### 2.5 Protocol Layer

**Purpose.** Normalize how agents communicate—bus message types, orchestration scripts, MCP tool surfaces.

**Backend dependencies.**

- `backend/ghostscript/` — lexer, parser, runtime
- `backend/swarm/bus.py` — `MsgType`, channel conventions
- `backend/mcp_server.py` — SSE MCP at `/mcp/sse`
- `backend/agent_loop.py` — agent execution loop

**OSS status.** Invocation flows through `oss/adapters/swarm.py`, which publishes to `#oss/tasks` and calls `agent_forge` or persona-backed inference. GhostScript is available in gateway but is not the default orchestration path.

**Maturity: Partial.** Messaging works; protocol normalization into `oss/schemas/message.py` is planned.

---

### 2.6 Evolution Layer

**Purpose.** Close the loop: propose change → evaluate → archive elite variants → optionally emit configuration patches.

**OSS implementation.**

- `oss/adapters/evolution.py` — records swarm cycles into KAIROS
- `oss/dna/omega_rewrite.py` — elite patch manifests on high scores

**Backend dependencies.**

- `backend/evolution/kairos.py`
- `backend/evolution/sage.py`
- `backend/evolution/map_elites.py`
- `backend/evolution/entity_drift.py`
- `backend/sage_enhanced.py`
- `continuous_evolution.py`, `run_sage_cycles.py`

**Maturity: Strong.** GH05T3's evolution spine is ahead of other layers. OSS re-exports and records; it does not duplicate SAGE logic.

---

### 2.7 Commerce Layer

**Purpose.** Connect subscriber revenue to platform capacity—webhooks, license gates, site-agent billing.

**Backend dependencies.**

- `backend/integrations/stripe_integration.py`
- `sovereignnation/payments.py`
- `backend/aethyro_license.py`
- `backend/site_agents/agents/stripe_agent.py`

**OSS status.** Facade planned at `oss/monetization/stripe.py`. Stripe events reach SwarmBus today; full NC settlement on payment is not wired.

**Maturity: Partial.**

---

### 2.8 Gateway Layer

**Purpose.** One outward-facing API and dashboard for operators, integrators, and remote nodes.

**Components.**

- `backend/gateway_v3.py` — SwarmBus, MCP, integrations (port 8002)
- `backend/server.py` — economy engine, Telegram, CFO (port 8001)
- `backend/v1_router.py` — `/v1/agents/{id}/invoke`
- `frontend/` — React dashboard, SwarmBus panel
- `run_stack.py` / `run.bat` — health-gated startup
- `supervisor.py` — extended economy stack orchestration

**OSS surface.** `oss/api/router.py` mounted at `/oss`. Gateway import is guarded—if OSS fails to load, the gateway still starts.

**Maturity: Operational.**

---

### 2.9 Environment Layer

**Purpose.** Run agents inside explicit simulated or narrative environments—not just chat sessions.

**Closest existing pieces.**

- `backend/integrations/story_editor.py` — stateful narrative sessions
- `frontier/` + `continuous_learner.py` — domain learning
- Training domain JSONL under `backend/training_data/`

**OSS status.** `oss/world/` reserved for Phase 2+. No runtime loop yet.

**Maturity: Not started** for OSS purposes.

---

## 3. Phase 1 Foundation — checklist

Phase 1 means: identity, messaging, memory hooks, evolution recording, gateway API, basic credits, mesh hooks.

| Capability | Status | Primary location |
|------------|--------|------------------|
| Agent identity & manifests | ✅ Complete | `agent_registry.py`, `personas.py` |
| Runtime invocation from manifests | ✅ Complete | `agent_forge.py`, `v1_router.py` |
| Swarm messaging bus | ✅ Complete | `swarm/bus.py` |
| Specialist roster | ✅ Complete | `swarm/agents.py` |
| Memory substrate | ✅ Dual stack | `memory/memory_palace.py`, `memory_cortex.py` |
| Evolution propose → evaluate → archive | ✅ Complete | `evolution/`, `run_sage_cycles.py` |
| API gateway & live UI | ✅ Complete | `gateway_v3.py`, `frontend/` |
| Credit / reward hooks | ✅ Complete | `economy/ledger.py`, `economy_bridge.py` |
| Job queue & agent labor | ✅ Complete | `agent_marketplace.py` |
| OSS genome model | ✅ Complete | `oss/dna/`, `oss/schemas/` |
| OSS collective orchestration | ✅ Complete | `oss/mind/`, `/oss/swarm/solve` |
| OSS Platform Credits | ✅ Complete | `oss/economy/neuro_coin.py` |
| External mesh discovery | ⚠️ Partial | `peer_registry.py`, Tailscale |
| Billing → credit settlement | ⚠️ Partial | Stripe → bus, not NC ledger |
| Orchestration language default | ⚠️ Partial | GhostScript optional |
| Registry ↔ genome sync | ❌ Pending | Adapter not yet shipped |
| Unified memory facade | ❌ Pending | `oss/adapters/memory.py` |
| External economy bridge | ❌ Pending | `:8081` adapter |
| Canonical mesh contract | ❌ Pending | `oss/grid/mesh.py` |

**Overall Phase 1 alignment: approximately 55–60%.** Evolution and gateway exceed Foundation bar. Genome unification, economy bridge, and mesh contract are the critical path to 80%+.

---

## 4. Recommended package evolution

Current layout (shipped):

```
oss/
  schemas/genome.py
  dna/{omni_dna,store,omega_rewrite}.py
  mind/{omni_mind,collective,selector,holographic}.py
  economy/{neuro_coin,desire}.py
  adapters/{swarm,evolution,marketplace}.py
  api/router.py
  cli/demo_swarm.py
```

Planned additions (Phase 2), in wiring order:

```
oss/
  README.md                          ✅
  BLUEPRINT.md                       ✅
  schemas/
    message.py                       ← SwarmBus + protocol normalization
    economy.py                       ← Ledger event schema
    mesh.py                          ← Canonical peer record
  adapters/
    registry.py                      ← Genome ↔ agent_registry sync  [PRIORITY]
    sovereign.py                     ← :8081 economy bridge
    memory.py                        ← Palace + cortex facade
  grid/
    mesh.py                          ← Mesh convergence implementation
  monetization/
    stripe.py                        ← Commerce facade
  world/
    runtime.py                       ← Environment loop (Phase 2+)
```

**Discipline rule:** If it defines meaning → `oss/schemas/`. If it calls existing code → `oss/adapters/`. If it serves HTTP → `oss/api/`. Never move inference, MongoDB, or SwarmBus internals into OSS.

---

## 5. Wiring sequence

Execute in this order to minimize rework:

| Step | Deliverable | Closes |
|------|-------------|--------|
| **1** | `oss/README.md` + `oss/BLUEPRINT.md` | Documentation debt |
| **2** | `oss/adapters/registry.py` | Genome ↔ registry split |
| **3** | `oss/schemas/{message,economy,mesh}.py` | Contract clarity |
| **4** | `oss/adapters/sovereign.py` | Three-way economy unification |
| **5** | `oss/grid/mesh.py` | Mesh convergence plan |
| **6** | `oss/adapters/memory.py` | Memory facade |
| **7** | Commit `oss/` + tests to main | Layer visibility in VCS |

---

## 6. API contract (Phase 1)

Base URL: `http://<host>:8002/oss`

| Endpoint | Behavior |
|----------|----------|
| `GET /health` | Layer liveness and version |
| `GET /agents` | Roster with collective snapshot |
| `GET /agents/{id}` | Full genome record |
| `POST /agents/{id}/evolve` | Score-driven trait adjustment |
| `GET /mind/state` | Shared orchestration state |
| `POST /swarm/solve` | Trait-gated collective execution |
| `GET /economy/stats` | NC balances + pending jobs |
| `POST /economy/delegate` | Marketplace job with NC reward |

Authentication follows gateway policy (`GH05T3_API_TOKEN` when set). OSS does not implement a separate auth plane in Phase 1.

---

## 7. Data persistence

| Store | Path | Contents |
|-------|------|----------|
| Genomes | `oss/data/genomes.db` | Trait payloads, lineage, registry linkage |
| Agent registry | `backend/data/agent_registry.db` | Manifests, prompts, marketplace metadata |
| Credits | `backend/economy/` (ledger files) | NC balances |
| Marketplace | `backend/data/` (marketplace DB) | Job queue |
| Evolution archive | `backend/evolution/kairos_log.jsonl` | Cycle history |
| Omega patches | `oss/data/omega_manifests/` | High-score configuration exports |

All `oss/data/*` runtime files are gitignored. Seed specialists on first boot via `demo_swarm.py --seed-only` or first `/oss/swarm/solve` call.

---

## 8. Testing & acceptance

Foundation acceptance criteria:

```bat
backend\.venv\Scripts\python.exe -m pytest tests\test_oss_*.py -q
backend\.venv\Scripts\python.exe oss\cli\demo_swarm.py --seed-only
curl http://localhost:8002/oss/health
```

Sixteen automated tests cover DNA persistence, swarm orchestration, Platform Credits, tier-2 patches, incentives, and holographic shards. A passing suite is required before any Phase 2 adapter merges.

---

## 9. Naming standard (external communication)

Use these terms in documentation, investor materials, and operator runbooks:

| Use | Avoid in formal docs |
|-----|----------------------|
| Sovereign Operations Stack (OSS) | Internal codename soup without definition |
| Genome Layer | Informal "DNA" without context |
| Orchestration Layer | "Collective consciousness" |
| Platform Credits (NC) | Mixed "credits / coins / rewards" |
| Performance Incentive Model | Acronym-first "DDRS" |
| Configuration patch manifest | "Omega rewrite" in customer-facing text |
| Specialist | "AI employee" |
| Registry manifest | "Prompt file" |

Code module names (`omni_dna`, `neuro_coin`, etc.) remain stable. Documentation carries the professional vocabulary.

---

## 10. Explicit non-goals (Phase 1)

- Voice synthesis, avatar rendering, real-time TTS pipelines
- Full mesh consensus protocols
- Multi-tenant isolation and per-org billing partitions
- Environment simulation runtime
- Rewriting `backend/swarm/` or `backend/evolution/`
- Kaggle or remote training orchestration (local training via `native/windows/train.bat` only)

---

## 11. Maturity summary

| Layer | Maturity | Note |
|-------|----------|------|
| Gateway | **Production-adjacent** | Dashboard, MCP, OSS mount |
| Evolution | **Production-adjacent** | KAIROS/SAGE/MAP-Elites proven |
| Orchestration | **Foundation-complete** | Swarm solve operational |
| Genome | **Foundation-partial** | Needs registry sync |
| Credit | **Foundation-partial** | Needs `:8081` bridge |
| Protocol | **Foundation-partial** | GhostScript not default |
| Commerce | **Foundation-partial** | Webhook ≠ NC settlement |
| Mesh | **Early** | Convergence doc open |
| Environment | **Not started** | Phase 2+ |
| Memory (unified) | **Early** | Dual stack, no facade |

---

## 12. Closing position

GH05T3 is not starting from zero. It is consolidating. The Sovereign Operations Stack exists so that consolidation happens in public view—with schemas, tests, and a gateway surface—rather than as accidental coupling inside `backend/`.

Phase 1 is not about spectacle. It is about **one identity model, one credit semantics, one mesh contract, one memory door**—each implemented as a thin facade over code that already runs on TatorTot, already serves the dashboard on port 3210, and already evolves on schedule through KAIROS.

Ship the registry bridge next. Everything else in Phase 2 becomes easier once agents have a single genome record the platform can point to, bill against, and route work through.

---

*Sovereign Operations Stack · GH05T3 Platform Architecture · v0.1.0*