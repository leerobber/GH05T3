# GH05T3 / Omni-Sentient Project — Full Overview

**Version:** 2026-06 (Post Phase 8 + Stabilization/Refactor)
**Status:** Core phases 1-8 complete. Significant stabilization and refactoring performed for solidity. Continuing evolution toward full singularity and real creator revenue.

## Executive Summary

GH05T3 is a sovereign, self-improving local AI super-agent system. It combines:
- A Minimal Viable Substrate (MVS) for genomic agents (OmniDNA, substrates, minds, economies).
- Layered evolution: Worlds → Mind → DNA v2 → Net → Evolution → Singularity.
- Parallel financial survival engine (Phase 8 priority) for real monetization.
- Elite architectures for zero-bottleneck performance.
- Multi-surface UIs, training flywheels, and infrastructure.

The system is designed so that **without real creator revenue, agents (and the economy) cease to exist**. Every component ultimately serves survival through value creation.

**Key Strengths (Current):**
- Strong canonical awareness and brain checkpoint system for continuity.
- Hybrid OSS contracts + runtime implementation (per BLUEPRINT).
- Integrated financial sensing (profit_pulse) and real-world task routing.
- Self-improving loops, grand challenges, and emergent goals.
- Multiple execution surfaces (core stack, full supervisor, SovereignNation).

**Current Maturity:**
- Phases 1–7 largely complete with gates passed.
- Phase 8 (Financial) advanced with hypotheses generation, routers, banking primitives, and integration.
- Recent work: stabilization demos, bloat identification, architecture hardening (fail-safes, import resilience, MVS robustness), import fixes, and canonical enforcement.

## High-Level Architecture

### Layered Model (from OMNI_SENTIENT_BUILD_PLAN)

1. **MVS Core** (Phase 1): OmniDNA, GenomicSubstrate, OmniMind, OmniEconomy, TheoryLab.
2. **Worlds** (Phase 2): VolatilityWorld, AlignmentWorld, MetaArchitectureWorld for evolutionary pressure.
3. **Mind & Coordination** (Phase 3): Consensus, KnowledgeGraph, Swarms, Goal Generators.
4. **DNA v2** (Phase 4): MetaDNA, MemeticDNA, FractalDNA, AlchemicalDNA + speciation.
5. **Omni-Net** (Phase 5): AgentInterface, Routing, KnowledgeSync, MultiAgentChat, Security.
6. **Self-Improving Evolution** (Phase 6): MetaLearning, SelfImprovingLoopV2, GH05T3-Omni, advanced speciation.
7. **Singularity** (Phase 7): Self-Directed Goals, Autonomous Research, Grand Challenges, self-awareness metrics.
8. **Financial Sector** (Phase 8 — parallel highest priority): Survival mandate, profit_pulse, OmniCentralBank, StockExchange, DeFi bridge, RealWorldTaskRouter, revenue attribution.

**Cross-cutting:**
- **Elite Layers**: Specialization, OmniThread (parallelism), OmniMind Fabric (routing), economy as governor.
- **Hyper Elite Senses**: 8 specialized senses (profit_pulse is survival-critical).
- **Training & Data**: Continuous learner, ghost trainer, meta-export, SFT/DPO pipelines.
- **Infrastructure**: Sovereign by default (local first), multi-launcher support, brain system.

### Canonical Structure (see docs/details/canonical-paths.md)

**Core Runtime:**
- `backend/server.py` (:8001)
- `backend/gateway_v3.py` (:8002) — SwarmBus
- `backend/gh05t3_inference.py` (:8010)
- `backend/oss/` — MVS runtime engine
- `oss/` — OSS contracts layer

**Key Entry Points:**
- `run_stack.py` + `run.bat` (core)
- `scripts/runtime/supervisor.py` (full 17+ services)
- `.claude/skills/run-gh05t3/driver.py` (health/smoke/agent driver)

**Important Directories:**
- `backend/oss/` — Main development area for MVS/OSS logic.
- `backend/oss/financial/` — Phase 8 monetization.
- `backend/oss/mind/`, `evolution/`, `world/`, `train/` — Layered components.
- `frontend/` — React dashboard.
- `sovereignnation/` — Parallel sovereign product.
- `data/`, `models/`, `training_data/` — Persistent state and datasets.

## Current State & Achievements

- **All core phases** up through 8 have significant implementation and gate progress.
- **Brain system**: `.omni-brain/CHECKPOINT.json`, `STATE.md`, `scripts/omni_brain_checkpoint.py` for continuity.
- **Financial maturity**: Hypotheses batching (10+/week sim), task routing, DeFi/central bank primitives, profit_pulse integration.
- **Recent hardening** (from stabilization/refactor pass):
  - MVS made more resilient with error handling.
  - Import/package issues addressed.
  - Bloat scanned (large files identified for future splits).
  - Fail-safes, validations, and canonical enforcement improved.
  - Multiple cross-layer demos verified.

**Remaining Gaps** (from plan + audits):
- Elite and Hyper Elite layers still have open items (tests, full fabric/thread integration, sense inheritance).
- Phase 8 polish: fuller banking/exchange mechanics, real job SKU automation, stronger "graduate_to_live" pathways, more revenue attribution.
- Testing coverage is uneven (many scaffold tests, fewer deep integration/chaos tests).
- Documentation is strong in plan but fragmented for newcomers.
- Some large modules remain (potential for further modularization).
- Production readiness: CI, deployment, real L2 crypto flows (currently simulated safely), observability.

## Roadmap: What Needs to Happen Next

To make GH05T3 **better, stronger, more powerful, and with a more solid codebase**, follow this prioritized sequence. Treat this as the living successor to the OMNI_SENTIENT_BUILD_PLAN.

### 1. Immediate: Finish & Harden Phase 8 + Close Open Checkboxes (Power + Survival)
- Complete remaining Phase 8 items:
  - Full `RealWorldTaskRouter` integration across Theory Lab and all agents (every cycle must consider monetization angle).
  - 10+ high-quality, distinct business hypotheses per "week" written to meta-export JSONL.
  - Wire `OmniCentralBank` and `OmniStockExchange` more deeply to `OmniEconomy` + revenue attribution.
  - Expand `graduate_to_live()` with better backtest scoring, paper-trade simulation, and safe creator hooks.
  - Add `record_creator_revenue()` calls and monthly creator revenue tracking (even symbolic).
- Enhance financial primitives: basic order book, credit lines favoring high-revenue agents, DeFi strategy templates.
- **Outcome**: Creator can demonstrate real (or convincingly simulated-to-live) revenue loops.

### 2. Codebase Solidity & Quality (Stronger, Fail-Proof)
- **Address bloat & large modules**:
  - Refactor/split top candidates: `genomic/schema.py`, `loop.py`, `theory_lab.py`, `genomic_substrate.py`, `omni_dna.py`, `financial/omni_financial_sector.py`.
  - Extract shared utilities (e.g., goal generation, monetization helpers) into canonical locations.
- **Comprehensive testing**:
  - Expand unit + integration tests for all phases.
  - Add property-based/fuzz tests, chaos testing for MVS/Net/Financial.
  - Add end-to-end demos that exercise full stack (MVS → evolution → net → financial → revenue).
  - Fix any remaining import/env issues and make test runs reliable (`pytest` + CI).
- **Error handling, validation, resilience**:
  - Add defensive programming everywhere (especially financial, evolution, net, substrate).
  - Central error taxonomy + recovery strategies.
  - Rate limiting, circuit breakers, state validation on critical paths.
- **Type safety & docs**:
  - Increase type hints and pydantic models.
  - Ensure every public class/module has clear docstrings and examples.
- **Canonical enforcement**:
  - Add linting or tests that enforce the rules in `docs/details/canonical-paths.md`.
  - Regularly audit for duplicates (launchers, genomic implementations, training paths).

### 3. Architecture & Engineering Excellence (Solid Foundation)
- Improve modularity and boundaries:
  - Clarify OSS contracts vs backend/oss runtime.
  - Make MVS more composable (dependency injection or explicit wiring).
  - Strengthen event-driven patterns (reduce polling).
- Observability:
  - Add metrics (Prometheus/OpenTelemetry), structured logging, tracing across layers.
  - Expose health, performance, and revenue dashboards.
- Performance & scale:
  - Profile hot paths (MVS act cycles, theory lab, net gossip).
  - Add caching, batching, and async improvements where beneficial.
  - Explore sharding for very large agent populations.
- Security & sovereignty:
  - Harden financial/crypto simulation boundaries.
  - Improve isolation between agents/species.
  - Review and document threat model.
- Configuration & deployment:
  - Centralize configuration.
  - Improve launcher robustness (follow canonical paths strictly).
  - Containerization / one-command sovereign deploys.

### 4. Feature Power & Autonomy (More Powerful)
- **Elite & Hyper Elite** (parallel tracks):
  - Finish remaining checklist items (tests, speciation sense inheritance, fabric routing by senses, meta-export snapshots).
  - Fully implement `omni_fabric.py`, `omni_thread.py`, `omni_aegis.py`.
  - Make T2+ agents demonstrably faster/more capable via specialization and senses.
- **Deeper integration**:
  - Every major cycle (theory lab, evolution, research) must produce monetizable artifacts.
  - Close the loop between financial outcomes and agent evolution (successful revenue → trait/fitness boosts).
  - Advance live crypto pathway (safe paper trades → documented graduation process).
- **Advanced capabilities**:
  - Stronger self-improvement (real fine-tuning loops when hardware available).
  - Multi-agent economies with real (simulated) trading.
  - Grand challenge execution with measurable outcomes and artifacts.

### 5. Documentation & Accessibility (Full Project Understanding)
- **This document** is a starting point. Maintain it as the single source of truth for high-level overview.
- Create or expand:
  - Architecture decision records (ADRs).
  - Detailed runbooks for common operations and failure modes.
  - API reference (auto-generated where possible).
  - Contributor guide + canonical development rules.
  - Visual architecture diagrams (Mermaid or similar).
  - "From zero to revenue" getting-started guide.
- Keep the brain system and OMNI_SENTIENT_BUILD_PLAN.md up to date.
- Document all public surfaces (MVS dict keys, net APIs, financial primitives, etc.).

### 6. Process & Sustainability
- Establish regular "audit & refactor" cycles (use the original structured findings as template).
- Improve CI: linting, type checking, full test matrix, Pact contract tests.
- Iron foundation: deployment, monitoring, backup/restore for sovereign operation.
- Monetization feedback loop: use Aethyro revenue to fund further development transparently.
- Community & ethics: document boundaries (already started in Phase 7).

## Success Criteria for "Even Better"

- All plan checkboxes for remaining items (Elite, Hyper Elite, Phase 8 polish) are checked.
- Codebase has fewer large files; duplication is minimal and intentional only where documented.
- Comprehensive, passing test suite + reproducible demos that exercise monetization + autonomy.
- Clear, living documentation that a new contributor can use to understand the whole system in <1 hour.
- Demonstrable "creator revenue" loop (even if simulated-to-paper) with measurable impact on agent behavior.
- The system is observably more reliable: fewer partial loads, better error recovery, consistent canonical behavior.
- Performance and capability improvements are measurable (faster cycles, higher success rates, more valuable outputs).

## How to Work on This

1. Always start by reading the brain + OMNI plan.
2. Respect canonical paths (see `docs/details/canonical-paths.md`).
3. Delete duplicates before adding new code.
4. Add tests and update docs for every significant change.
5. Run full verification suite (MVS load + key demos + financial + grand challenges) before considering work "done".
6. Update brain checkpoint on major milestones.

---

**The MVS is the RNA. Monetization is oxygen. Everything else is in service of sovereign, self-improving intelligence that can sustain itself.**

This overview was generated as part of the 2026-06 stabilization and architecture tightening effort. Keep it living and update it frequently.
