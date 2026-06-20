"""
Provider verification for OSS using TestClient mount pattern.

This test:
- Starts the provider using the exact same mount as gateway_v3.py
- Provides a /_pact/provider_states endpoint for state setup
- Runs verification against local pacts or broker (if configured)

Run:
  PACT_BROKER_URL=... PACT_BROKER_TOKEN=... \
    python -m pytest tests/test_oss_provider_verify.py -q
"""
import os
import sys
import threading
import time
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import uvicorn

from oss.api.router import router as oss_router
from oss.pact.provider_states import router as pact_states_router

# Defensive loading for Verifier
# SKIP_PACT=1 → always skip on any OS
# FORCE_PACT=1 → attempt import even on Windows (may cause DLL fatal errors)
def _get_verifier():
    if os.environ.get("SKIP_PACT") == "1":
        return None
    if sys.platform.startswith("win") and os.environ.get("FORCE_PACT") != "1":
        return None
    try:
        from pact import Verifier
        return Verifier
    except Exception:
        return None

Verifier = _get_verifier()

pytestmark = pytest.mark.skipif(
    Verifier is None,
    reason="pact-python not available or FFI failed (use FORCE_PACT=1 on Windows)",
)

def start_test_server(app: FastAPI, port: int = 0):
    """Start uvicorn in a thread and return base url + shutdown event."""
    if port == 0:
        port = 8765  # fixed for simplicity in tests
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(0.8)  # give it a moment
    return f"http://127.0.0.1:{port}", server

@contextmanager
def provider_app():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    app.include_router(pact_states_router)

    base_url, srv = start_test_server(app)
    try:
        yield base_url
    finally:
        # uvicorn server shutdown is tricky in thread; for CI we let process die
        pass

def test_provider_verification():
    broker_url = os.environ.get("PACT_BROKER_URL")
    token = os.environ.get("PACT_BROKER_TOKEN")

    with provider_app() as provider_url:
        verifier = Verifier(
            provider="gh05t3-oss",
            provider_base_url=provider_url,
        )

        if broker_url:
            # Verify against broker pacts for the consumer
            output, logs = verifier.verify_with_broker(
                broker_url=broker_url,
                broker_token=token,
                consumer_version_selectors=[{"latest": True, "tag": "ci"}],
                publish_verification_results=True,
            )
        else:
            # Local fallback: verify against generated pacts/ dir if present
            pacts_dir = "pacts"
            if not os.path.isdir(pacts_dir):
                pytest.skip("No broker and no local pacts/ — skipping provider verification")
            pact_paths = [
                os.path.join(pacts_dir, f)
                for f in os.listdir(pacts_dir)
                if f.endswith(".json")
            ]
            output, logs = verifier.verify_pacts(
                *pact_paths,
                provider_states_setup_url=f"{provider_url}/_pact/provider_states",
            )

        assert output == 0, f"Provider verification failed:\n{logs}"
