---
name: test-gh05t3
description: Run, interpret, and diagnose the full unified GH05T3/Aethyro test suite. Use this skill whenever the user asks about running tests, test suite status, pytest output, whether tests are passing, how to run a subset of tests, what skipped tests mean, or wants to add/fix a test. Also triggers on "check test status", "are the tests green", "why is this test failing", "pytest gh05t3", "291 tests", "test coverage". This skill knows the exact single command, the unified testpaths structure, WSL integration tests, and every common failure mode with its fix.
---

# GH05T3 Test Suite

All tests live under `tests/` at the repo root. `pytest.ini` sets `testpaths = tests` — there is only one test directory now. Never run `python -m pytest backend/tests/` — that directory is a stub and collects nothing.

## The One Command

```powershell
cd C:\Users\leer4\GH05T3
python -m pytest -q
```

That's it. No env prefix needed — the root `conftest.py` auto-sets `AETHYRO_SKIP_LICENSE=1` and `GH05T3_TEST_MODE=1` before any test file is imported.

**Expected baseline result:** `291 passed, 15 skipped, 0 failures`

---

## What the 15 Skips Mean

| Skip bucket | Count | Condition to un-skip |
|---|---|---|
| WSL integration | 6 | `$env:WSL_SERVICES_UP = "1"` + `wsl_start.sh` running |
| Live server (backend/gateway) | 9 | `$env:REACT_APP_BACKEND_URL = "http://localhost:8002"` + full stack running |

Neither bucket is a failure — they're gating correctly on service availability.

---

## Running Subsets

```powershell
# One file
python -m pytest tests/test_advanced_training.py -v

# One test function
python -m pytest tests/test_advanced_training.py::test_advanced_training_subsystems -v

# WSL integration tests (requires WSL services up)
$env:WSL_SERVICES_UP = "1"
python -m pytest tests/test_wsl_integration.py -v

# Live server tests (requires full stack running)
$env:REACT_APP_BACKEND_URL = "http://localhost:8002"
python -m pytest tests/test_gh05t3.py tests/test_gh05t3_phase2.py tests/test_gh05t3_phase3.py tests/test_gh05t3_phase4.py tests/test_swarm.py -v

# OSS modules only (fastest, no live deps)
python -m pytest tests/test_oss_*.py -q

# With verbose failure output
python -m pytest -q --tb=short

# Show all skips with reasons
python -m pytest -v --no-header -rN 2>&1 | Select-String "SKIP"
```

---

## Test File Map

| File | What it tests | Live dep? |
|---|---|---|
| `test_advanced_training.py` | Binary ledger, swarm bus, ghost protocol, gateway AST, config | No |
| `test_mesh_contract.py` | gateway_v3 peer registry contract | No |
| `test_civilization_kernel.py` | OSS kernel: agents, rewards, orchestrator, sandbox | No |
| `test_oss_contract.py` | MVS cycle: KAIROS + genome + training | No |
| `test_oss_*.py` (many) | Individual OSS subsystems | No |
| `test_wsl_integration.py` | WSL backend+gateway health, round-trip latency | WSL only |
| `test_gh05t3*.py` | Full stack HTTP integration | Backend URL |
| `test_swarm.py` | SwarmBus live delegation | Backend URL |

---

## sys.path and conftest Architecture

```
C:\Users\leer4\GH05T3\
├── conftest.py          ← LOADED FIRST by pytest — sets AETHYRO_SKIP_LICENSE,
│                           GH05T3_TEST_MODE, adds backend/ and repo root to sys.path
├── pytest.ini           ← testpaths = tests (single entry)
└── tests/
    ├── conftest.py      ← unified markers + live/WSL skip logic
    ├── test_*.py        ← all 57 test files (moved from tests/ + backend/tests/)
    └── (no __init__.py) ← intentionally removed; __init__.py caused package-mode import issues
```

**Why no `tests/__init__.py`:** When it existed, pytest used package-import mode, which changed when `sys.path` mutations took effect relative to module-level imports. Tests that do `import gateway_v3` at module level (like `test_mesh_contract.py`) would fail with `ModuleNotFoundError: No module named 'swarm'`. Removing it restores direct-import mode where the root conftest's `sys.path` setup applies before any test file is imported.

---

## Common Failure Modes and Fixes

### `ModuleNotFoundError: No module named 'swarm'` (or any bare backend module)
The root `conftest.py` didn't run, or `backend/` isn't in sys.path.
```powershell
# Verify conftest is present and correct
Get-Content C:\Users\leer4\GH05T3\conftest.py
# Should show: sys.path.insert(0, str(_BACKEND)) where _BACKEND = .../GH05T3/backend
```
Never run pytest from inside `backend/` or `tests/` — always from the repo root.

### `SystemExit: 1` during collection (gateway_v3 license gate)
`AETHYRO_SKIP_LICENSE` wasn't set. Check that `conftest.py` at repo root sets it.
```python
# conftest.py must contain:
os.environ.setdefault("AETHYRO_SKIP_LICENSE", "1")
```

### `AssertionError: N subsystem checks failed` in `test_advanced_training_subsystems`
The test records pass/fail for each subsystem internally and raises at the end. Get the detail:
```powershell
python -m pytest tests/test_advanced_training.py -v -s 2>&1 | Select-String "FAIL|PASS"
```
Common causes: compile error in a backend .py file (SyntaxError), missing file the test expects (gateway_v3.py at `BACKEND/gateway_v3.py`), or a dead port in the dead-port env vars.

### `5 passed` instead of `291 passed` (only test_mesh_contract + test_advanced_training found)
You ran `python -m pytest backend/tests/` — that directory is now a stub. Run from repo root with no path arg.

### `tests/__init__.py exists` warning or package import errors
Delete `tests/__init__.py` if it reappears — it should not exist.
```powershell
Remove-Item C:\Users\leer4\GH05T3\tests\__init__.py -ErrorAction SilentlyContinue
```

### Ghost/NoLLMError in `test_advanced_training_subsystems`
The test patches `ghost_llm._env_key` to return `""` to block all provider keys. If this fails, check:
```python
# In test_advanced_training.py, around line 140:
with _patch("ghost_llm._env_key", return_value=""):
    # chat_once() call here
```
The patch prevents `_env_key()` from reading the real `.env` file via `dotenv_values()`. `os.environ.pop()` alone is not enough because `ghost_llm` re-reads the file directly.

---

## Adding a New Test

1. Place it in `tests/test_<module_name>.py`
2. Use bare imports (`from evolution.sage import SAGE`) — `backend/` is already in sys.path
3. Or use `backend.` prefix (`from backend.oss.core.chronos_ledger import ChronosLedger`)
4. For tests needing a live ledger, use `tmp_path` fixture:
```python
def test_ledger_write(tmp_path):
    from backend.oss.core.chronos_ledger import ChronosLedger
    ledger = ChronosLedger(filename=tmp_path / "test.bin", capacity=100)
    ledger.write_agent(0, (0.5,)*7, maturity=1, fitness=0.8)
    data = ledger.read_agent(0)
    assert abs(data["fitness"] - 0.8) < 0.01  # float16 precision
    ledger.close()
```

---

## Verified State (2026-06-20)

```
291 passed, 15 skipped, 0 failures in ~3m 51s
- 6 WSL skips: WSL_SERVICES_UP not set
- 9 live-server skips: REACT_APP_BACKEND_URL not set
- 0 failures
```
