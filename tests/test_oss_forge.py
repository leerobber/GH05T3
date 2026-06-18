"""Omni Forge agency training layer tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.forge.agency import AgencyForge
from oss.forge.corpus import seed_corpus
from oss.forge.omni_lex import decode_turn, encode_turn, shard_to_chatml
from oss.forge.quality_gate import score_shard
from oss.forge.schemas import ForgeDomain, QualityTier, TrainingShard
from oss.forge.store import ForgeStore
from oss.api.router import router as oss_router


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    db = tmp_path / "forge.db"
    monkeypatch.setattr("oss.forge.store._DB_PATH", db)
    import oss.forge.store as store_mod
    store_mod._init()
    return ForgeStore()


def test_seed_corpus_passes_quality_gate():
    for shard in seed_corpus():
        verdict = score_shard(shard, min_tier=QualityTier.SILVER)
        assert verdict.keep is True
        assert verdict.tier != QualityTier.TRASH


def test_quality_gate_trashes_junk():
    junk = TrainingShard(
        shard_id="j1",
        domain=ForgeDomain.DEFAULT,
        system="",
        user="test",
        assistant="N/A",
        source="test",
    )
    verdict = score_shard(junk)
    assert verdict.tier == QualityTier.TRASH
    assert verdict.keep is False


def test_omni_lex_roundtrip():
    shard = seed_corpus()[0]
    wire = encode_turn(
        genome_id="oracle",
        domain=shard.domain,
        signal=0.9,
        system=shard.system,
        user=shard.user,
        assistant=shard.assistant,
    )
    parsed = decode_turn(wire, system=shard.system)
    assert parsed is not None
    assert parsed.user == shard.user
    assert parsed.assistant == shard.assistant
    assert "<|im_start|>user" in shard_to_chatml(shard)


def test_agency_cycle_keeps_seeds(isolated_store, monkeypatch):
    monkeypatch.setattr("oss.forge.agency.get_store", lambda: isolated_store)
    monkeypatch.setattr("oss.forge.store.get_store", lambda: isolated_store)
    export_dir = Path(__file__).parents[1] / "backend" / "data" / "training"
    monkeypatch.setattr("oss.forge.train_bridge._EXPORT_DIR", export_dir)

    agency = AgencyForge()
    agency.store = isolated_store
    record = agency.run_cycle(include_pipeline=False, include_seeds=True, min_tier=QualityTier.SILVER)
    assert record.kept >= len(seed_corpus())
    assert record.trashed == 0
    assert record.status == "complete"


def test_forge_api_status():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)
    resp = client.get("/oss/forge/preflight")
    assert resp.status_code == 200
    body = resp.json()
    assert "rules" in body
    assert len(body["rules"]) >= 4


def test_forge_submit_rejects_short():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)
    resp = client.post(
        "/oss/forge/submit",
        json={"domain": "code", "user": "short", "assistant": "also short"},
    )
    assert resp.status_code == 422