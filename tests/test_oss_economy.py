"""OSS Sprint 2 — Neuro-Coin + marketplace tests."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


@pytest.fixture
def neuro_coin(tmp_path, monkeypatch):
    backend = _ROOT / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    db = tmp_path / "palace.db"
    monkeypatch.setenv("ECONOMY_DB_PATH", str(db))
    monkeypatch.setenv("MARKETPLACE_DB_PATH", str(db))

    import economy.ledger as ledger_mod
    import agent_marketplace as mkt_mod
    ledger_mod._DB_PATH = db
    ledger_mod._ledger = None
    mkt_mod._DB_PATH = db
    mkt_mod.JobQueue._instance = None

    from oss.economy.neuro_coin import NeuroCoin
    return NeuroCoin()


def test_neuro_coin_earn_and_balance(neuro_coin):
    bal = neuro_coin.earn("FORGE", 100, reason="test reward")
    assert bal == 100
    assert neuro_coin.balance("FORGE") == 100


def test_neuro_coin_transfer(neuro_coin):
    neuro_coin.earn("FORGE", 50, reason="seed")
    result = neuro_coin.transfer("FORGE", "CODEX", 20, reason="collab")
    assert result["amount"] == 20
    assert neuro_coin.balance("FORGE") == 30
    assert neuro_coin.balance("CODEX") == 20


def test_neuro_coin_insufficient_transfer(neuro_coin):
    with pytest.raises(ValueError, match="insufficient"):
        neuro_coin.transfer("FORGE", "CODEX", 10)


@pytest.mark.anyio
async def test_post_job_via_neuro_coin(neuro_coin):
    job_id = await neuro_coin.post_job(
        task="audit auth module",
        tags=["SENTINEL"],
        reward=50,
    )
    assert len(job_id) >= 8

    from oss.adapters.marketplace import get_job, list_jobs
    job = get_job(job_id)
    assert job is not None
    assert job["status"] == "pending"
    assert "SENTINEL" in job["tags"]

    pending = list_jobs(status="pending", limit=5)
    assert any(j["id"] == job_id for j in pending)


def test_neuro_coin_stats(neuro_coin):
    neuro_coin.earn("NEXUS", 25, reason="ops")
    stats = neuro_coin.stats()
    assert stats["currency"] == "NC"
    assert "all_balances" in stats