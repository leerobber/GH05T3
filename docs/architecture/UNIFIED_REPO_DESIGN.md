# Unified Repo — Audit & Design Plan

Scope: `leerobber/GH05T3` (1,315 files, ~128k Python LOC, 115 MB) and `ITFactorTech/sovereign-core` (206 files, ~26k Python LOC, 18 MB).
Status: **plan only. No code moved.** Measured on 2026-10-03 from a bare venv (fastapi/pytest/numpy only).

---

## 1. Audit

### sovereign-core — a small, disciplined kernel + gateway

**Good**
- Honest docs: README separates Live / Code-ready / Designed. 6 ADRs, including a regression post-mortem.
- Has CI (5 workflows incl. CodeQL), Dockerfile, pyproject, compose.
- Gateway is a coherent unit: router, health, metrics, auction, ledger, context layer, WebSocket, auth, Iron Dome middleware, `/v1` OpenAI-compat.
- `src/` (668 LOC, zero dependencies): S-ISA opcodes, semantic words, scheduler, agent state. Clean enough to be a real kernel.
- KAIROS has real Critic/Verifier gates and a fixed scoring rule.
- Tests: **479 pass / 76 skip** in a bare env; the README claims 570 with full deps.

**Bad**
- `chromadb` and `backoff` are imported by 43+5 tests but are **not declared in `pyproject.toml`** (only in `requirements.txt`). `pip install .[gateway]` gives a broken install. Python floor disagrees: pyproject/Docker = 3.12, README = 3.11+.
- Safety is mostly paper: only the Kill Switch is enforced; Ethics, Sim, CLARA, Iron Dome, GhostRecall are designed or code-ready, not live (the README says so).
- 8 stale tests (`test_sovereign_stack.py` asserts gateway port 8080; the real port is 9000; `test_main.py` proxy tests fail).
- Root clutter: 8 single-file directories (`seance/`, `spawner/`, `strange_loop/`, `feynman/`, `team/`, `kairos/` next to `gateway/kairos*.py`, …) and two chat servers.
- `SOVEREIGN_STATUS.md` is a stale personal memory file (dated 2026-04, contains name, email and a wrong-handle note). Not repo material.
- ROADMAP depends on synchronizing 5 repos. That is the problem, not the plan.

### GH05T3 — a wide product and training platform

**Good**
- Hard-won training knowledge: LoRA collapse rules, 4-bit NF4, Blackwell/cu128 quirks, local-only pipeline. This is the most valuable non-code asset.
- `ghost_llm.py` multi-provider router with a cost-free mode, a SwarmBus with circuit breaker and peer registry, personas, MoE router, an OpenAI-compatible inference server, Stripe and story-editor integrations.
- Most mature genome system (MVS / OmniDNA / GenomicSubstrate) plus `oss/ecosystem` with real telemetry.
- Real frontend (React + Vite, ~73 JSX components), Rust `gml_kernel` and `omni_bme` router.
- Broad tests: **554 pass / 32 skip**. The 7 failures and 6 errors I saw were missing optional deps (`ribs`, `pandas`, `chromadb`) plus 3 `test_soft_mode_gates` failures I have not diagnosed.
- Security hygiene is documented: the hardcoded Slack secret was fixed. I found no live keys in the current tree. History still contains them; rotation is external.

**Bad**
- **No CI at all** (`.github/` holds only an `__init__.py`).
- Binary and state files in git: 4 `.pt` checkpoints, a 6.8 MB `tokenizer.json` copied about 6 times, `.bin`/`.db` state. Roughly 115 MB checkout for 128k LOC.
- 4 parallel evolution systems (MVS/OmniDNA, `oss/ecosystem`, the 5-trait genome in GH05T3-Sovereign, KAIROS in sovereign-core). Its own inventory doc calls this "unresolved".
- Duplication by design: `oss/` vs `backend/oss/`, two OmniDNAs, two genomic substrates, and 3 UI surfaces plus sovereign-ui.
- 222 `__init__.py` files, many in non-package dirs (`.grok/`, `.codex/`). Five AI-tool config trees (`.agents`, `.grok`, `.codex`, `.omni-brain`, `.emergent`) live in the product repo.
- Monoliths: `gateway_v3.py` (1,873 lines), `server.py` (1,988 lines, requires MongoDB).
- Docs drift: CLAUDE.md says CRA and `REACT_APP_*`; README says Vite. The financial sector is auto-disabled by a safety engine.
- Product, marketing and ops mixed in (`sovereignnation/` 67 files, outreach scripts, installers, NSIS/Inno).

### The shared cause
Each repo is half of one system. sovereign-core is the **control plane** (route, auction, ledger, verify). GH05T3 is the **intelligence plane** (models, training, agents, genome, UI). They were forked and re-forked instead of layered, so the same ideas now exist 2–4 times each.

---

## 2. Design: one repo, layered, one-way dependencies

Working name: `sovereign` (placeholder). Monorepo, `uv`/pip workspace, one CI.

```
sovereign/
├── kernel/        ← sovereign-core/src        (no deps, S-ISA, scheduler, agent state)
├── gateway/       ← sovereign-core/gateway    (router, health, auction, ledger, context, auth, /v1)
├── safety/        ← iron_dome, kill switch, ethics/sim/CLARA gates, ghost_protocol
├── evolution/     ← ONE genome + ONE loop (see §3)
├── memory/        ← memory_palace + ghostrecall (single SQLite/Chroma interface)
├── agents/        ← GH05T3 swarm bus, personas, MoE router, agent registry
├── llm/           ← ghost_llm router + inference server + provider adapters
├── training/      ← train_local.py, rules, dataset fetch (CLAUDE.md rules become tests)
├── ui/            ← ONE frontend (React+Vite, GH05T3's)
├── native/        ← Windows/Linux/Termux install + launchers
├── rust/          ← gml_kernel, omni_bme (optional, feature-flagged)
├── products/      ← avery/ (persona, story editor, Stripe), sovereignnation/ (client, landing)
├── docs/          ← ADRs + one status table (Live / Code-ready / Designed)
└── tests/         ← mirrors the layout; contract tests for each seam
```

**Dependency rule (enforced by import-linter in CI):**
`kernel ← safety ← memory ← llm ← agents ← evolution ← gateway ← products/ui`. Nothing imports upward. Products are leaves.

**Ports (one table, one config module):** gateway **9000** is the single public entry. Internal services (inference 8010, verifier 8011, CPU fallback 8012, Lemonade 13305) hide behind it. The 8001/8002 split goes away; `server.py` is absorbed into the gateway's routers and Mongo is dropped in favour of SQLite (already used by the palace) unless a specific feature proves it needs Mongo.

**What each repo contributes**

| Capability | Take from | Why |
|---|---|---|
| Kernel, gateway, auction, ledger, context, health/metrics | sovereign-core | Smaller, cleaner, tested, has CI |
| KAIROS critic/verifier gates | sovereign-core | Real gates, fixed scoring |
| Iron Dome, GhostRecall | sovereign-core (code) + GH05T3 `memory/ghostrecall.py` (reconcile) | Two versions exist; pick one and test it end-to-end |
| LLM router, inference server, personas, SwarmBus, MoE | GH05T3 | Only place they exist |
| Training pipeline and rules | GH05T3 | Irreplaceable know-how |
| Genome / speciation | GH05T3 MVS/OmniDNA as the base | Most mature |
| Frontend | GH05T3 | Only real UI |
| Stripe, story editor, Avery | GH05T3 → `products/` | Leaf product, not core |
| Docs discipline, ADRs, status table | sovereign-core | Keep this culture |

**Left behind:** model checkpoints and adapters (to HF Hub or Releases), `data_disabled/`, `.grok`/`.codex`/`.omni-brain`/`.emergent`/`.agents`, `_future_backup`, `test_reports`, stale launchers, the 5-trait genome fork, `SOVEREIGN_STATUS.md`, empty `__init__.py` in non-packages, the `sovereign-ui` duplicate, the legacy `swarm_legacy.py`.

---

## 3. Decision needed: the four evolution systems

Recommended: **(a) one `GenomicSubstrate`**; MVS/OmniDNA owns traits, the 5-trait binary/ternary architecture genes become additional trait types, and KAIROS becomes the *proposal/verification pipeline* that mutates it (KAIROS = process, MVS = state). One fitness ledger, which is already the gateway ledger. Rejected: keeping all four joined by HTTP (that is the status quo that caused this).

Honest feasibility: merging is moderate work (schema mapping plus tests). The real unknown is whether the genome has *measurable fitness signal* on real tasks. Today it scores synthetic contexts (`unit_test`, `synthetic_trading`). Without a real benchmark, unifying it just produces one elegant system that selects for nothing. Build the benchmark in Phase 2 before polishing the loop.

---

## 4. Migration plan

History decision: **do not carry GH05T3's history** (21 MB `.git`, leaked secrets, binaries). Start fresh from the final trees. Keep both old repos, archived and read-only, linked from the README. Sovereign-core's history is small and can be subtree-merged if you want it.

| Phase | Output | Exit test |
|---|---|---|
| **0 Decide** (1 day) | Name, license (sovereign-core is AGPL-3.0; GH05T3 has a commercial product, so confirm), host repo, which Python (3.12) | Written ADR |
| **1 Skeleton** | Layout above, pyproject with *all* deps declared per extra, CI (lint, types, tests, import-linter, secret scan, size cap on files >1 MB), pre-commit | CI green on empty skeleton |
| **2 Core transplant** | kernel + gateway + safety + memory from sovereign-core, with failing tests fixed or deleted (port 9000) | ≥570 tests pass in a clean `pip install .[all]` |
| **3 Intelligence transplant** | llm, agents, training, training rules as tests (assert `use_reentrant=False`, no fp16 adapter cast, collapse bounds), one UI | `/v1/chat/completions` round-trip through gateway → router → local model; UI boots |
| **4 Evolution merge** | §3, plus a real benchmark (see §3) | A KAIROS cycle changes a genome and the fitness change is measured on a held-out task |
| **5 Products** | Avery, Stripe, SovereignNation as leaves | Billing webhook test; zero core imports from products |
| **6 Archive** | Archive old repos, rotate leaked secrets, purge `data_disabled` | Fresh clone < 20 MB |

---

## 4b. What's possible, unproven, impossible

- **Provably possible:** everything in Phases 1–3. These are well-understood software engineering and both suites already mostly pass.
- **Theoretically possible, unproven:** the self-improving loop producing *net-positive* changes on real tasks (Darwin Gödel Machine-style systems report gains, but on narrow coding benchmarks with large compute). On an 8 GB RTX 5050 expect small models and slow cycles.
- **Not achievable as claimed:** "zero latency / no limits". An 8 GB GPU runs 7B 4-bit models; larger models fall back to cloud, which breaks "zero-egress". The gateway already encodes this tradeoff honestly; keep it visible.
- **Risk:** recursive self-modification without enforced gates. Today only the Kill Switch is live. Mitigation: make Ethics + Sim gates *blocking and tested* in Phase 2, before the evolution merge in Phase 4. Sandbox mutation output; never auto-deploy to the live path.

## 5. Path to enhancements (after Phase 6)
1. Wire real fitness from the training pipeline (eval loss on a held-out set) into the genome ledger, so evolution has a signal.
2. AMD 780M and CPU verifier tier as a second-opinion gate before a mutation deploys.
3. Formal spec for S-ISA (already has `docs/isa_spec.md`) plus property tests; Lean/TLA+ later only for the kill-switch and ledger.
4. Tailscale mesh as a first-class transport so TatorTot and the Termux node (TIA) are just more backends.

## 6. Questions that change the plan
1. **Which repo is the host?** Recommend a new empty repo; second choice is sovereign-core (it already has CI and clean history).
2. **License.** AGPL core vs commercial product leaves — decide before Phase 1.
3. **Is SovereignNation (the services business) staying in the same repo?** Recommended: no, leaf directory now, own repo later.
4. **Do you actually need MongoDB?** I found no hard evidence it must stay.
