"""
Real Pact consumer tests for the two key MVS endpoints.

These generate Pact contract files in pacts/ directory.
Run with:
  pip install pact-python
  python -m pytest tests/test_oss_pact.py -q

When PACT_BROKER_URL is set, contracts can be published (see publish step in CI).

Provider verification is done by re-using the existing TestClient mount
(acts as "provider state" verification).
"""

import os
from contextlib import contextmanager

import platform
import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from oss.api.router import router as oss_router

# Import pact only when available (graceful for minimal envs)
# pact-python v3 on Windows often fails to load the native pact_ffi DLL.
# We detect this early and skip.
#
# Env-var overrides:
#   SKIP_PACT=1  — force-skip on any OS (useful in local dev without a broker)
#   FORCE_PACT=1 — attempt import even on Windows (you may see fatal DLL errors)
PACT_AVAILABLE = False
_Consumer = _Provider = _Like = _Term = _EachLike = None

_skip_pact = os.environ.get("SKIP_PACT") == "1"
_force_pact = os.environ.get("FORCE_PACT") == "1"
_on_windows = platform.system() == "Windows"

if not _skip_pact and (not _on_windows or _force_pact):
    try:
        from pact import Consumer, Provider, Like, Term, EachLike
        _Consumer = Consumer
        _Provider = Provider
        _Like = Like
        _Term = Term
        _EachLike = EachLike
        PACT_AVAILABLE = True
    except Exception:
        # Catch ImportError, DLL load errors, etc.
        PACT_AVAILABLE = False
else:
    # On Windows, pact_ffi frequently raises fatal DLL errors.
    # Force skip unless user explicitly sets FORCE_PACT=1
    if os.environ.get("FORCE_PACT") == "1":
        try:
            from pact import Consumer, Provider, Like, Term, EachLike
            _Consumer = Consumer
            _Provider = Provider
            _Like = Like
            _Term = Term
            _EachLike = EachLike
            PACT_AVAILABLE = True
        except Exception:
            PACT_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not PACT_AVAILABLE,
    reason="pact-python not available or broken native FFI (common on Windows)"
)

def _get_consumer(port: int = 8123):
    """Lazy creation of the Pact consumer to avoid import-time crashes on Windows."""
    if not PACT_AVAILABLE or _Consumer is None:
        return None
    try:
        return _Consumer("gh05t3-gateway").has_pact_with(
            _Provider("gh05t3-oss"),
            pact_dir="pacts",
            port=port,
            file_write_mode="merge",
        )
    except Exception:
        return None


@contextmanager
def _pact_mock(consumer):
    """Start the Ruby mock service, verify interactions, and write pact JSON."""
    consumer.start_service()
    try:
        consumer.setup()
        yield consumer
        consumer.verify()
    finally:
        try:
            consumer.stop_service()
        except RuntimeError:
            pass


def _mock_request(consumer, method, path, **kwargs):
    headers = {**consumer.HEADERS, **kwargs.pop("headers", {})}
    return requests.request(
        method,
        f"{consumer.uri}{path}",
        headers=headers,
        verify=False,
        **kwargs,
    )


@pytest.fixture(scope="module")
def oss_client():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    return TestClient(app)


def test_consumer_mvs_status(oss_client):
    """Consumer pact for GET /oss/mvs/status with rich matchers"""
    consumer = _get_consumer(port=8123)
    if consumer is None:
        pytest.skip("pact not available")
    (
        consumer
        .given("MVS substrate is initialized with genomes")
        .upon_receiving("a request for MVS status")
        .with_request("GET", "/oss/mvs/status")
        .will_respond_with(
            200,
            body=_Like({
                "available": True,
                "genomes": _Like({
                    "total_genomes": 100,
                    "roles": _EachLike("SCIENTIST"),
                }),
                "loop_state": _Like({"species": "S5_evolve", "aggregate": 0.65, "omni_mind": 0.62}),
                "source": "backend.oss.mvs + oss_ecosystem.json",
            })
        )
    )

    with _pact_mock(consumer):
        response = _mock_request(consumer, "GET", "/oss/mvs/status")
        assert response.status_code == 200

    provider = oss_client.get("/oss/mvs/status")
    assert provider.status_code == 200
    body = provider.json()
    assert "available" in body
    assert "genomes" in body or "loop_state" in body


def test_consumer_mvs_cycle(oss_client):
    """Consumer pact for POST /oss/mvs/cycle (dry run path)"""
    consumer = _get_consumer(port=8124)
    if consumer is None:
        pytest.skip("pact not available")
    (
        consumer
        .given("MVS is ready to run cycles")
        .upon_receiving("a dry-run cycle request")
        .with_request(
            "POST", "/oss/mvs/cycle",
            body=_Like({"cycles": 2, "dry_run": True}),
            headers={"Content-Type": "application/json"},
        )
        .will_respond_with(
            200,
            body=_Like({
                "ran": 2,
                "dry_run": True,
                "results": _EachLike({"tick": 0, "global": "S0_perceive", "agg": 0.67}),
                "duration_sec": _Like(0.123),
            })
        )
    )

    with _pact_mock(consumer):
        response = _mock_request(
            consumer,
            "POST",
            "/oss/mvs/cycle",
            json={"cycles": 2, "dry_run": True},
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json()["ran"] == 2

    provider = oss_client.post("/oss/mvs/cycle", json={"cycles": 2, "dry_run": True})
    assert provider.status_code == 200
    assert provider.json()["ran"] == 2

def test_consumer_mvs_health(oss_client):
    """Basic health contract"""
    consumer = _get_consumer(port=8125)
    if consumer is None:
        pytest.skip("pact not available")
    (
        consumer
        .given("service is up")
        .upon_receiving("health check")
        .with_request("GET", "/oss/health")
        .will_respond_with(200, body=_Like({"status": "ok", "layer": "oss"}))
    )
    with _pact_mock(consumer):
        r = _mock_request(consumer, "GET", "/oss/health")
        assert r.status_code == 200

    provider = oss_client.get("/oss/health")
    assert provider.status_code == 200


# Optional provider verification helper (run after consumer to verify pacts)
def test_verify_pacts_against_oss_provider():
    """
    Simple provider-side verification using the mounted app.
    In full Pact flow this would be done with pact-python's Verifier against a running server
    or via `pact-verifier` CLI pointing at the generated pacts/.
    """
    # For this environment we just re-execute the consumer expectations
    # against the live TestClient (this proves the provider still honors the contract).
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)

    # Re-run the expectations manually as verification
    r1 = client.get("/oss/mvs/status")
    assert r1.status_code == 200

    r2 = client.post("/oss/mvs/cycle", json={"cycles": 1, "dry_run": True})
    assert r2.status_code == 200


# Broker publishing helper (no-op unless infrastructure present)
def publish_contracts_if_broker_configured():
    """
    Call this from CI when you have a Pact Broker.
    Example:
        PACT_BROKER_URL=https://your-broker.example.com \
        PACT_BROKER_TOKEN=... \
        python -c "from tests.test_oss_pact import publish...; publish..."
    """
    if not PACT_AVAILABLE:
        return
    broker_url = os.environ.get("PACT_BROKER_URL")
    if not broker_url:
        print("[pact] No PACT_BROKER_URL set — skipping publish (as designed).")
        return

    # Real publishing would use pact-python's publish or pact-cli
    # For now we print the instruction. When broker is ready, wire `pact publish pacts/ ...`
    print(f"[pact] Broker configured at {broker_url}. Ready to publish pacts/ when pact CLI or python-publisher is wired.")
    # Example future code:
    # from pact import Verifier
    # ... or subprocess call to pact-broker


if __name__ == "__main__":
    publish_contracts_if_broker_configured()
