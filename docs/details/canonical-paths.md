# GH05T3 Canonical Paths & Repo Structure

> Source of truth for layout, launchers, UIs, and genomic/MVS layers.
> Generated from structured audit (2026-06). Duplication is **intentional** in the BLUEPRINT hybrid model (OSS contracts + backend runtime), but stale/broken copies must be removed.

See also:
- [RUN_ORDER.md](../RUN_ORDER.md)
- [OMNI_SENTIENT_BUILD_PLAN.md](../OMNI_SENTIENT_BUILD_PLAN.md)
- [README.md](../../README.md)

## Genomic / MVS Layer

| Role | Canonical path | Why |
|------|----------------|-----|
| Molecule/locus genome schema + bridge to OmniDNA | `backend/oss/genomic/` | Has `bridge.py`, `evolution_tuner.py`, `sync_genome_to_omni_dna()`; used by `backend/oss/mvs.py`, `tests/test_genomic_schema.py` |
| MVS runtime substrate (AgentHandle, register_genome) | `backend/oss/genomic_substrate.py` | Used by `theory_lab.py`, `mvs.py`, `swarm_contracts.py`, `test_mvs_core.py` |
| OSS contract substrate | `oss/substrate/genomic.py` | Used by `oss/api/router.py`, `oss/lab/*`, `oss/integration/living_loop.py` |
| Trait dict / OmniDNA schema | `oss/dna/omni_dna.py` (contract) + `backend/oss/omni_dna.py` (runtime impl) | Per `oss/BLUEPRINT.md` hybrid model |
| Genome schemas | `oss/schemas/genome.py` | Canonical OSS contracts |

## Core GH05T3 Runtime

| Role | Canonical path |
|------|----------------|
| Backend API | `backend/server.py` → :8001 |
| Gateway + SwarmBus + OSS mount | `backend/gateway_v3.py` → :8002 |
| Inference | `backend/gh05t3_inference.py` → :8010 |
| Thin Python launchers (sys.path fix) | `launch_backend.py`, `launch_gateway.py` |

## Launchers / Orchestration

| Use case | Canonical path |
|----------|----------------|
| Core stack (documented, tested) | `run_stack.py` + `run.bat` |
| Full sovereign economy (17+ services) | `scripts/runtime/supervisor.py` via `native/windows/START_ALL.bat` or `native/windows/START.bat` |
| Linux manual | `native/linux/start.sh` |
| Agent health/smoke driver | `.claude/skills/run-gh05t3/driver.py` |

**Notes:**
- Use `python run_stack.py --review` (the `--review` flag lives here, not bare `run.bat`).
- Supervisor status: `http://localhost:8090/status`
- Stop supervisor: `python scripts/runtime/supervisor.py --stop`

## Frontend / UIs (multiple surfaces)

| UI | Canonical path | Port |
|----|----------------|------|
| Main React dashboard | `frontend/src/App.jsx` → `frontend/build/` | 3210 |
| Genome lab static dashboard | `frontend/genome_dashboard.html` | 7720 (supervisor) |
| SovereignNation client + Ollama proxy | `sovereignnation/serve.py` + `sovereignnation/client/` | 7861 |
| SovereignNation landing | `sovereignnation/landing/` | 8765 (supervisor) |

## Training Ops

| Role | Canonical path |
|------|----------------|
| Continuous learner / flywheel | `scripts/training/continuous_learner.py`, `scripts/training/ghost_trainer.py` (911 LOC) |
| Integrated backend training | `backend/training/` pipeline (`pipeline.py`, `finetune.py`) |
| RunPod remote training | `scripts/training/runpod_launcher.py` |

---

## DUPLICATES & REMOVAL PLAN (from audit)

High priority items were addressed in cleanup pass:

1. **backend/genomic/ vs backend/oss/genomic/** — Migrated consumers, removed legacy tree.
2. Genomic substrate twins — keep both for now (converge later per BLUEPRINT).
3. Launcher / supervisor entry points — retired stale ones (launcher.py, main.py, START_GH05T3.bat, native/windows/run.bat).
4. Broken script paths — fixed callers to use `scripts/runtime/*` and `scripts/training/*`.
5. Frontend duplicates — removed `GH05T3Dashboard_v3.jsx`; deduped sovereign landing.
6. Native vs scripts runtime — removed native/windows copies of whisper etc.
7. Training duplicates — converged where possible.
8. OmniDNA duplicate — intentional hybrid (contract + impl).

### Bloat removed
- `scripts/_archive/`
- `*.disabled`
- `sovereignnation/client/sovereignnation.zip`
- `sovereignnation/client/landing/` (dup)
- `backend/_launch_*_nolicense.bat`
- `frontend/package-lock.json` (kept yarn.lock as primary per run_stack)
- Cache artifacts (gitignore'd)

### Port hygiene
- Canonical gateway: **8002** (everywhere except any remaining stale refs).
- Update any 8003 references.

---

## Cleanup Status

See git history / commit messages for exact removals and path fixes performed as part of Phase 4 prep + structure hygiene.

For future detail docs in this space:
- Put long-form architecture deep-dives in `docs/architecture/`
- Put operator runbooks in `docs/runbooks/`
- Put audit reports, decision records, and detailed findings here under `docs/details/`

Last updated: 2026-06-20 (by Grok agent following audit report).

## Actions Performed (Phase 4 prep + hygiene pass)

- Created `docs/details/`, `docs/architecture/`, `docs/runbooks/` as space for detailed project docs.
- Fixed path references in `run_stack.py`, `run.bat`, `scripts/runtime/serve_frontend.py`, `native/windows/stop.bat`.
- Migrated `sovereignnation/sovereign_interface.py` + 2 tests to `backend.oss.genomic`.
- Deleted entire `backend/genomic/` legacy tree.
- Retired stale: `launcher.py`, `main.py`, `native/windows/{START_GH05T3.bat,run.bat}`, nolicense bats, `start_v3.sh.disabled`.
- Removed native dup scripts (whisper/voice/tray).
- Frontend: deleted `GH05T3Dashboard_v3.jsx`, `client/landing/` dup, `client/sovereignnation.zip`, `frontend/package-lock.json`.
- Purged `scripts/_archive/` (15 files).
- Updated docs (README, RUN_ORDER, oss/README, frontend/README) + new canonical-paths.md.
- Verified imports for migrated genomic layer succeed.

Stale/broken references should now point to canonicals. Run `python run_stack.py --review` to inspect ports.
Next: consider converging substrate twins + training dups in later pass; proceed with Phase 4 DNA v2 implementation per OMNI_SENTIENT_BUILD_PLAN.md .

