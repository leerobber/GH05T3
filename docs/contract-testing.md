# Contract Testing with Pact (GH05T3 OSS)

This document describes how GH05T3 uses consumer-driven contract testing with Pact to protect the `/oss` surface (especially the MVS endpoints) between the gateway, OSS, and SovereignCore.

## Implementation status (canonical paths)

| Item | Status | Location |
|------|--------|----------|
| Consumer tests | Done | `tests/test_oss_pact.py` |
| Provider verification | Done | `tests/test_oss_provider_verify.py` |
| Publish + retry/backoff | Done | `scripts/publish_pacts.py` |
| Can-I-Deploy gate | Done | `scripts/can_i_deploy.py` |
| Broker health | Done | `scripts/broker_health.py` |
| CI jobs | Done | `.github/workflows/ci.yml` |
| Cross-platform runner | Done | `scripts/pact/run.sh` (WSL), `scripts/pact/run.ps1` (Windows) |
| Staging verify | Partial | `scripts/staging_verify.py` (health only; broker verify TBD) |
| Mesh contract tests | Separate | `backend/tests/test_mesh_contract.py` (skipped in backend CI gate) |

**Do not add** duplicate publish helpers in tests or a separate `ci/publish_pacts.sh` — Python scripts above are the single source of truth.

## Quick Start (Local)

### WSL / Linux / Git Bash
```bash
bash scripts/pact/run.sh consumer
bash scripts/pact/run.sh provider
bash scripts/pact/run.sh publish    # no-op without broker secrets
bash scripts/pact/run.sh can-i-deploy
```

### Windows PowerShell
```powershell
.\scripts\pact\run.ps1 consumer
.\scripts\pact\run.ps1 provider
.\scripts\pact\run.ps1 publish
.\scripts\pact\run.ps1 can-i-deploy
```

### 1. Run consumer tests (generate pacts)
```bash
pip install pact-python
python -m pytest tests/test_oss_pact.py -q
```

Pact files will be written to `pacts/` (gitignored).

### 2. Run provider verification (TestClient)
```bash
python -m pytest tests/test_oss_provider_verify.py -q
```

On Windows, pact FFI often fails unless you set `$env:FORCE_PACT = "1"` or run consumer/provider in WSL/Linux CI.

This mounts the real OSS router exactly as `gateway_v3.py` does and verifies against the pacts.

## Broker Configuration

Set these environment variables (usually GitHub secrets):

- `PACT_BROKER_URL`
- `PACT_BROKER_TOKEN`

When present, the CI will:
- Publish pacts from the consumer job
- Verify pacts in the provider job
- Support can-i-deploy queries

If the variables are absent, all steps gracefully become no-ops or use local artifacts.

## CI Jobs (see .github/workflows/ci.yml)

1. **backend** — normal tests + OSS smoke (always runs)
2. **pact-consumer** — runs `tests/test_oss_pact.py`, generates pacts, publishes if broker configured
3. **pact-provider** — runs provider verification (TestClient or against broker)
4. **can-i-deploy** — queries broker; fails promotion on unverified pacts (skips or warns if no broker)
5. **staging-smoke** (manual) — health check + verification against real staging URL

## Matchers Used

We use Pact's flexible matchers so contracts are not brittle:

- `Like(...)` — structure + type matching
- `Term(...)` — regex for fields like durations or IDs
- `EachLike(...)` — arrays

See `tests/test_oss_pact.py` for current expectations on:
- `GET /oss/mvs/status`
- `POST /oss/mvs/cycle`

## Common Failures & Fixes

| Symptom                        | Likely Cause                          | Fix |
|--------------------------------|---------------------------------------|-----|
| 404 on provider verification   | Wrong mount prefix or state not set   | Ensure provider state handler sets up MVS genomes |
| Mismatch on "aggregate"        | Floating point or new field added     | Use `Like(0.65)` or `Term` matcher |
| Broker 401/403                 | Wrong token or URL                    | Check secrets |
| Pact file not found            | Consumer job didn't run or artifacts not uploaded | Check job dependencies |
| Port conflict in provider test | Test server already running           | Use unique port or let uvicorn choose |

## Troubleshooting

**Check broker health**
```bash
python scripts/broker_health.py
# or
curl -f $PACT_BROKER_URL/health
```

**Run only pact tests**
```bash
python -m pytest -k "pact or oss_pact or oss_contract" -q
```

**Publish manually**

Unix / Git Bash / WSL:
```bash
PACT_BROKER_BASE_URL=... PACT_BROKER_TOKEN=... \
  python scripts/publish_pacts.py pacts/ $(git rev-parse HEAD) ci
```

PowerShell (Windows):
```powershell
$env:PACT_BROKER_BASE_URL = "https://your-org.pactflow.io"
$env:PACT_BROKER_TOKEN = "your-token-here"
python scripts/publish_pacts.py pacts/ $(git rev-parse HEAD) ci
```

**Can-I-Deploy check**

Unix:
```bash
PACT_BROKER_BASE_URL=... PACT_BROKER_TOKEN=... \
  python scripts/can_i_deploy.py \
    --consumer gh05t3-gateway --provider gh05t3-oss \
    --version $(git rev-parse HEAD)
```

PowerShell:
```powershell
$env:PACT_BROKER_BASE_URL = "..."
$env:PACT_BROKER_TOKEN = "..."
python scripts/can_i_deploy.py `
    --consumer gh05t3-gateway `
    --provider gh05t3-oss `
    --version $(git rev-parse HEAD)
```

## Emergency Override

If the broker is down and you must promote:
- Set the `can-i-deploy` job to `if: false` temporarily, or
- Run with `--strict=false` equivalent (current scripts default to allow on unreachable).

Always follow up with a manual verification once the broker recovers.

## Adding New Endpoints

1. Add a consumer test in `tests/test_oss_pact.py` using `Like`/`Term`.
2. Update provider state setup in `tests/test_oss_provider_verify.py` if needed.
3. Run locally to generate an updated pact.
4. Let CI publish + verify.

This keeps the iron foundation: contracts are the source of truth for integration between GH05T3, OSS/MVS, and SovereignCore.