# Contract Testing with Pact (GH05T3 OSS)

Consumer-driven contracts protect the `/oss` surface (especially MVS) between **gh05t3-gateway** (consumer) and **gh05t3-oss** (provider).

## Architecture

```
tests/test_oss_pact.py     →  pacts/*.json  →  tests/test_oss_provider_verify.py
   (Pact mock server)          (git-ignored)      (TestClient = gateway mount)

tests/test_oss_contract.py — lightweight shape smoke (no Pact FFI, runs in backend job)

scripts/
  broker_health.py, publish_pacts.py, can_i_deploy.py, staging_verify.py
scripts/pact/run.sh | run.ps1 — cross-platform entrypoints
```

| Secret present | Consumer job | Provider job | Can-I-Deploy |
|----------------|--------------|--------------|--------------|
| Both set | Generate + **publish** | Verify + publish results | **Runs** |
| Missing | Generate only | Verify from artifact | Skipped (no-op) |

**Pacticipant names (broker):** `gh05t3-gateway` / `gh05t3-oss` — do not rename without broker migration.

## Implementation status

| Item | Location |
|------|----------|
| Consumer tests | `tests/test_oss_pact.py` |
| Provider verification | `tests/test_oss_provider_verify.py` |
| Contract shape smoke | `tests/test_oss_contract.py` |
| Provider states | `oss/pact/provider_states.py` → `POST /_pact/provider_states` |
| CI | `.github/workflows/ci.yml` |
| Runners | `scripts/pact/run.{sh,ps1}` |

## Quick start (local)

### WSL / Linux
```bash
bash scripts/pact/run.sh consumer
bash scripts/pact/run.sh provider
bash scripts/pact/run.sh publish
bash scripts/pact/run.sh can-i-deploy
```

### Windows PowerShell
```powershell
.\scripts\pact\run.ps1 consumer
.\scripts\pact\run.ps1 provider
```

### Manual
```bash
pip install pact-python
PYTHONPATH=backend python -m pytest tests/test_oss_pact.py -q
PYTHONPATH=backend python -m pytest tests/test_oss_provider_verify.py -q
PYTHONPATH=backend python -m pytest tests/test_oss_contract.py -q
```

On Windows, set `$env:FORCE_PACT = "1"` or run Pact tests in WSL/Linux CI.

## GitHub secrets

| Secret | Used by |
|--------|---------|
| `PACT_BROKER_URL` | publish, verify, can-i-deploy, staging-smoke |
| `PACT_BROKER_TOKEN` | same |
| `STAGING_BASE_URL` | staging-smoke (`workflow_dispatch`) |

Free tier: [PactFlow](https://pactflow.io). Local `.env` accepts `PACT_BROKER_BASE_URL` or `PACT_BROKER_URL`.

## CI pipeline

```
backend → pact-consumer → pact-provider → can-i-deploy (if broker)
                              ↓
                    (manual) staging-smoke
```

Trigger staging smoke:
```bash
gh workflow run ci.yml -f run_staging_smoke=true --ref main
```

### Jobs

1. **backend** — unit tests + `test_oss_contract.py` shape smoke
2. **pact-consumer** — `test_oss_pact.py`, artifact `pacts-${{ github.sha }}`, optional publish
3. **pact-provider** — `test_oss_provider_verify.py` (fails on contract break)
4. **can-i-deploy** — matrix check consumer→provider (skipped without broker)
5. **staging-smoke** — `staging_verify.py` against `STAGING_BASE_URL`
6. **fullstack-mock** — `scripts/oss_smoke.py`

## Scripts reference

### Publish
```bash
# Legacy positional
python scripts/publish_pacts.py pacts/ "$(git rev-parse HEAD)" ci

# Flags
python scripts/publish_pacts.py \
  --pacts-dir pacts/ \
  --consumer-version "$(git rev-parse HEAD)" \
  --branch "$(git branch --show-current)" \
  --tag ci
```

### Can-I-Deploy

Matrix mode (CI default):
```bash
python scripts/can_i_deploy.py \
  --consumer gh05t3-gateway \
  --provider gh05t3-oss \
  --version "$(git rev-parse HEAD)" \
  --tag ci \
  --strict
```

PactFlow environment mode:
```bash
python scripts/can_i_deploy.py \
  --pacticipant gh05t3-oss \
  --version "$(git rev-parse HEAD)" \
  --to-environment production
```

Record deployment after promote:
```bash
python scripts/can_i_deploy.py \
  --pacticipant gh05t3-oss \
  --version "$VERSION" \
  --record-deployment production
```

### Staging verify
```bash
python scripts/staging_verify.py \
  --provider-url "$STAGING_BASE_URL" \
  --broker-url "$PACT_BROKER_URL" \
  --broker-token "$PACT_BROKER_TOKEN" \
  --provider-name gh05t3-oss \
  --consumer-tag ci
```

## Matchers

Use `Like`, `Term`, `EachLike` in `tests/test_oss_pact.py` — assert consumer-relevant fields only.

Current interactions: `GET /oss/mvs/status`, `POST /oss/mvs/cycle`, `GET /oss/health`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Provider 404 | OSS router mounted at `/oss`; check provider states |
| Broker 401 | Token scope read+write |
| Stale pacts | `rm -rf pacts/` and re-run consumer tests |
| Port 1234 in use | `PACT_MOCK_PORT=1235` or kill stale mock |
| Windows FFI fail | `SKIP_PACT=1` or WSL / `FORCE_PACT=1` |

**Broker health:** `python scripts/broker_health.py`

**Stale pact cleanup:**
```bash
rm -rf pacts/
PYTHONPATH=backend python -m pytest tests/test_oss_pact.py -q
```

## Adding endpoints

1. Consumer test in `tests/test_oss_pact.py` with matchers.
2. Provider state in `oss/pact/provider_states.py` if needed.
3. Shape assertion in `tests/test_oss_contract.py` (optional).
4. CI publishes + verifies automatically when broker is wired.

Do not add duplicate publish helpers — `scripts/publish_pacts.py` is canonical.