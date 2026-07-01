# Iron Foundation Roadmap

Sequenced checklist to convert the MVS spine into a production-grade, independently deployable stack.
Execute in order — do not jump to Omni-OS v7 layers until each phase is green in CI.

**Evolution layer (canonical):** [`OMNI_SENTIENT_BUILD_PLAN.md`](OMNI_SENTIENT_BUILD_PLAN.md) — phased MVS → OmniWorld → OmniMind → DNA v2 → Omni-Net → Singularity, plus elite zero-bottleneck architecture and master implementation checklist.

**Canonical tooling:** `scripts/pact/run.sh` / `run.ps1`, `scripts/oss_smoke.py`, `docs/contract-testing.md`

---

## Pillar 1 — Contract & Integration Testing (High)

| # | Task | Status | Owner / Notes |
|---|------|--------|---------------|
| 1.1 | Pact consumer tests for `/oss/mvs/status` and `/oss/mvs/cycle` | Done | `tests/test_oss_pact.py` |
| 1.2 | Provider verification (TestClient mount = gateway pattern) | Done | `tests/test_oss_provider_verify.py` |
| 1.3 | Publish + can-i-deploy broker scripts | Done | `scripts/publish_pacts.py`, `can_i_deploy.py` |
| 1.4 | CI jobs: consumer → provider → can-i-deploy → fullstack-mock | Done | `.github/workflows/ci.yml` |
| 1.5 | Cross-platform Pact runners (WSL + Windows) | Done | `scripts/pact/run.{sh,ps1}` |
| 1.6 | Configure GitHub secrets: `PACT_BROKER_URL`, `PACT_BROKER_TOKEN` | **Todo** | Required for broker gating |
| 1.7 | Staging provider verify against live URL | **In progress** | `scripts/staging_verify.py` + `/_pact/provider_states` on gateway |
| 1.8 | SovereignCore bridge Pact contracts (gateway → sovereign-core) | **Todo** | After bridge API stabilizes |
| 1.9 | Loose matchers only — no internal business rules in contracts | Ongoing | See `docs/contract-testing.md` |

---

## Pillar 2 — CI/CD, Gated Deploys & Observability (High)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | Build → unit → contract → smoke in every PR | Done | `backend` + `pact-*` + `fullstack-mock` jobs |
| 2.2 | MVS smoke: `ensure_mvs_seeded` + dry cycle in CI | Done | `scripts/oss_smoke.py` |
| 2.3 | Prometheus metrics: cycle duration + marketplace failures | **In progress** | `oss/observability/metrics.py`, `/oss/metrics` |
| 2.4 | SLOs: cycle success rate, bridge latency, trait drift alerts | **Todo** | Define after 2.3 baselines |
| 2.5 | Distributed traces: gateway → MVS → SovereignCore | **Todo** | OpenTelemetry or structured trace IDs |
| 2.6 | Health probes authoritative for rollbacks | **Todo** | Wire K8s/ArgoCD or supervisor restart policy |
| 2.7 | Staged promotion: staging-smoke workflow_dispatch | Partial | Needs `STAGING_BASE_URL` secret |
| 2.8 | Dependency scanning (SCA) in CI | **Todo** | pip-audit or Dependabot |
| 2.9 | Container image signing | **Todo** | When images are published |

---

## Pillar 3 — Runtime Hardening & Governance (Medium)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Central `ensure_oss_paths()` — one import helper | Done | `oss/utils/paths.py` — migrate stragglers |
| 3.2 | Idempotent `ensure_mvs_seeded()` | Done | `backend/oss/loop.py` |
| 3.3 | Marketplace ops: guarded try/except + telemetry | **In progress** | `backend/oss/omni_economy.py` |
| 3.4 | Feature flags for experimental adapters | **Todo** | Env-driven toggles in `oss/adapters/` |
| 3.5 | `agent_registry` deprecated shim; personas canonical | **Todo** | Document in `INTEGRATIONS.md` |
| 3.6 | Network egress policy as code | **Todo** | Allowed external URLs list |
| 3.7 | Least-privilege RBAC for adapters | **Todo** | Sovereign + marketplace bridges |

---

## Phased Evolution (sequential — do not skip)

You are between **Phase 1.5 → Phase 2.0**. Do not start quantum/fractal/holographic DNA, soul bonds, or Omni-Net at 1M users until prior phases are CI-green.

### Phase 2.0 — ONE complete OmniWorld (AlignmentWorld first)

| # | Task | Status |
|---|------|--------|
| 2.0.1 | `AlignmentWorld` with interactive scenario evaluation | Done | `backend/oss/world/alignment_world.py` |
| 2.0.2 | Theory Lab prefers AlignmentWorld (weighted selection) | **In progress** | `backend/oss/lab/theory_lab.py` |
| 2.0.3 | Real divergence metric (not forced 0.18 demo) | Done | `measure_group_divergence`, `attempt_speciation_with_pressure` |
| 2.0.4 | ASCII phylogeny from speciation events | **In progress** | `render_phylogeny_ascii()` |
| 2.0.5 | Export world scores to meta-evolution JSONL | Done | `data/theory_lab_meta.jsonl` |

### Phase 2.5 — OmniMind v1.5

| # | Task | Status |
|---|------|--------|
| 2.5.1 | Weighted consensus across theorist proposals | Partial | `loop.py` privileged theorist set |
| 2.5.2 | Canonical memory tagging | Partial | `canonical: True` on high scores |
| 2.5.3 | Goal generator v2 | **Todo** | `backend/oss/mind_goals.py` |

### Phase 3.0 — OmniDNA v2.0 (meta-DNA + memetic DNA only)

| # | Task | Status |
|---|------|--------|
| 3.0.1 | Memetic share between theorists | Done | `theory_lab.py` score > 0.8 |
| 3.0.2 | Meta-DNA evolution rules per species | Partial | `speciation.py` per-species `meta_dna` |
| 3.0.3 | Reproductive isolation (`should_isolate`) | Done | `speciation.py` |

### Phase 4.0 — Omni-Net Beta (100–500 users)

| # | Task | Status |
|---|------|--------|
| 4.0.1 | Theory broadcast on high scores | Done | `omni_net.py` |
| 4.0.2 | Controlled beta rollout + rate limits | **Todo** |

### Phase 5.0 — Omni-Evolution v2.0 (self-improving loop)

| # | Task | Status |
|---|------|--------|
| 5.0.1 | Evaluation harness feeds training metrics | Partial | `EvaluationHarness` in theory_lab |
| 5.0.2 | Closed loop: harness → curriculum → trainer | **Todo** |

### Phase 6.0 — Species divergence experiments

| # | Task | Status |
|---|------|--------|
| 6.0.1 | Speciation phase runner | Done | `backend/oss/speciation_phase.py` |
| 6.0.2 | Remove forced demo speciation; use real threshold | Done | `speciation_phase.py` |
| 6.0.3 | GH05T3 persona mapping (DIV/MEM/COH/ARC/ECO) | **Todo** | Lore + ops naming |

---

## Quick wins (this week)

- [x] Pact consumer tests for `/oss/mvs/status` and `/oss/mvs/cycle`
- [x] CI smoke: `ensure_mvs_seeded` + `run_cycle(dry_run=True)`
- [ ] Prometheus: `gh05t3_mvs_cycle_duration_seconds`, `gh05t3_marketplace_failures_total`
- [ ] GitHub secrets for Pact broker
- [ ] Pick one GH05T3 runtime (Windows supervisor **or** WSL — not both on 8001/8002)
- [ ] Resolve `CHANGELOG.md` stash conflict from pact cleanup

---

## Operational mesh (dual-runtime)

See **`scripts/mesh/README.md`** for full guide.

| Use case | Runtime | Start |
|----------|---------|-------|
| Full 16-service production mesh | **Windows** | `native\windows\START_ALL.bat` |
| OSS/MVS + CUDA in WSL | **WSL** | `bash scripts/wsl_start.sh` |

**Rule:** One stack on ports 8001/8002/8090. Detect: `bash scripts/mesh/select_runtime.sh`

**sovereign-core probes:** `GH05T3_RUNTIME=wsl` (default) or `=windows` when supervisor runs on Windows.

---

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Brittle Pact contracts | Matchers only; assert consumer-relevant fields |
| Pipeline complexity | Minimal path first: build → unit → contract → staging |
| Observability noise | Start with 3 signals: cycle success, marketplace errors, bridge latency |
| Vision overload | This doc is the sequence — one phase at a time |