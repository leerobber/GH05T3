"""OSS Prometheus metrics tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.api.router import router as oss_router
from oss.observability.metrics import (
    record_cycle,
    record_marketplace_failure,
    record_marketplace_success,
    metrics_payload,
)


def test_record_cycle_and_marketplace_counters():
    record_cycle(0.42, dry_run=True, outcome="ok")
    record_marketplace_success("buy")
    record_marketplace_failure("list")

    body, media_type = metrics_payload()
    if media_type.startswith("text/plain"):
        text = body.decode() if isinstance(body, bytes) else body
        assert "gh05t3_mvs_cycle_duration_seconds" in text
        assert "gh05t3_marketplace_failures_total" in text
    else:
        assert "note" in body


def test_oss_metrics_endpoint():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)
    r = client.get("/oss/metrics")
    assert r.status_code == 200