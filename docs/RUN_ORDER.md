# GH05T3 / Omni-Sentient — Run Order

Canonical startup sequence. **One stack** on core ports (8001/8002/8090/8100).

> Full canonical paths, UIs, launchers, and removal decisions: see [docs/details/canonical-paths.md](details/canonical-paths.md).

## Mode A — Dev stack (fastest)

```bash
cd GH05T3
python run_stack.py --smoke   # optional health check
python run_stack.py
```

| Order | Service | Port |
|-------|---------|------|
| 1 | MongoDB | 27017 |
| 2 | Backend (`backend/server.py`) | 8001 |
| 3 | Gateway (`backend/gateway_v3.py`) | 8002 |
| 4 | Frontend static | 3210 |

## Mode B — Full supervisor (production)

```bash
cd GH05T3
python scripts/runtime/supervisor.py
```

| Order | Service | Port |
|-------|---------|------|
| 1 | Economy API | 8081 |
| 2 | MongoDB | 27017 |
| 3 | Backend | 8001 |
| 4 | Gateway | 8002 |
| 5 | Frontend | 3210 |
| 6 | Continuous learner | — |
| 7 | CMD listener | — |
| 8 | Amplifier | — |
| 9 | Sovereign serve | 7861 |
| 10 | Payments | 7862 |
| 11 | Phi service | 8112 |
| 12 | Pipeline backend | 8099 |
| 13 | **Sovereign interface** | **8100** |
| 14 | **Genome Lab UI** | **7720** |
| 15 | NPU embed | 8111 |
| 16 | SAGE engine | 8098 |
| 17 | Landing | 8765 |
| 18 | Cloudflare tunnels | — |
| 19 | Tunnel watcher | — |
| — | Supervisor status | **8090** |

**Dashboard:** http://localhost:7720/genome_dashboard.html (requires :8100 + :7720)

## Mode C — SovereignNation standalone

```bash
cd GH05T3/sovereignnation
./start.bat    # Windows
```

## Mode D — Omni build / tests (no servers)

```bash
cd GH05T3
MVS_DRY_RUN=1 pytest tests/test_mvs_core.py tests/test_mvs_dry_run.py tests/test_volatility_world.py \
  tests/test_meta_export_validation.py tests/test_theory_lab_volatility.py tests/test_loyalty_proposals.py \
  tests/test_genomic_schema.py tests/test_omni_mind_phase3.py tests/test_phase2_gate.py -v
MVS_DRY_RUN=1 python scripts/profile_mvs_p95.py
python scripts/omni_brain_checkpoint.py
```

## Stop

```bash
python scripts/runtime/supervisor.py --stop
# or native/windows/stop.bat
```