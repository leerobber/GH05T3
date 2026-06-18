"""Omni Forge agency training layer tests."""
from __future__ import annotations

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
from oss.forge.domains import list_domains, resolve_domain, search_domains
from oss.forge.genetics import transcribe_strand, build_elite_profile
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


def test_scientific_domain_titles_exist():
    domains = list_domains()
    keys = {d["key"] for d in domains}
    assert "machine_learning_theory" in keys
    assert "mycological_network_economics" in keys
    assert "genomics_inspired_ai" in keys
    titles = {d["title"] for d in domains}
    assert "Machine Learning Theory" in titles
    assert "Mycological Network Economics" in titles


def test_legacy_domain_alias_resolves():
    assert resolve_domain("security") == ForgeDomain.CYBER_DEFENSE_SCIENCE
    assert resolve_domain("fungi_economics") == ForgeDomain.MYCOLOGICAL_NETWORK_ECONOMICS
    assert resolve_domain("code") == ForgeDomain.COMPUTATIONAL_SCIENCE


def test_domain_search_finds_ai_ml():
    hits = search_domains("transformer")
    assert any(h["key"] == "deep_learning_architectures" for h in hits)


def test_seed_corpus_passes_quality_gate():
    for shard in seed_corpus():
        verdict = score_shard(shard, min_tier=QualityTier.SILVER)
        assert verdict.keep is True
        assert verdict.tier != QualityTier.TRASH


def test_elite_seeds_transcribe_to_strands():
    elite = [s for s in seed_corpus() if s.metadata.get("elite_breed")]
    assert len(elite) >= 5
    for shard in elite:
        verdict = score_shard(shard)
        strand = transcribe_strand(shard, verdict.score, verdict.tier)
        assert strand.capability_amplifier > 2.0
        assert "elite_breed_locus" in strand.crispr_targets


def test_elite_profile_targets_100b_effective():
    shards = [
        transcribe_strand(s, 0.9, QualityTier.ELITE, rank=i)
        for i, s in enumerate([x for x in seed_corpus() if x.metadata.get("elite_breed")][:6])
    ]
    profile = build_elite_profile(shards, physical_params_b=8.0)
    assert profile["effective_capability_b"] >= 50.0
    assert profile["paradigm"] == "omni_strand_sft"


def test_quality_gate_trashes_junk():
    junk = TrainingShard(
        shard_id="j1",
        domain=ForgeDomain.GENERAL_COGNITION,
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
    assert "<|im_start|>user" in shard_to_chatml(shard)


def test_agency_cycle_keeps_seeds(isolated_store, monkeypatch):
    monkeypatch.setattr("oss.forge.agency.get_store", lambda: isolated_store)
    monkeypatch.setattr("oss.forge.store.get_store", lambda: isolated_store)
    export_dir = Path(__file__).parents[1] / "backend" / "data" / "training"
    monkeypatch.setattr("oss.forge.train_bridge._EXPORT_DIR", export_dir)
    monkeypatch.setattr("oss.forge.elite_train._EXPORT_DIR", export_dir)

    agency = AgencyForge()
    agency.store = isolated_store
    record = agency.run_cycle(include_pipeline=False, include_seeds=True, min_tier=QualityTier.SILVER)
    assert record.kept >= len(seed_corpus())
    assert record.trashed == 0
    assert record.status == "complete"


def test_forge_domains_api():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)
    resp = client.get("/oss/forge/domains?q=quantum")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


def test_forge_submit_accepts_legacy_slug():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)
    resp = client.post(
        "/oss/forge/submit",
        json={
            "domain": "computational_science",
            "user": "How do I design a thread-safe queue?",
            "assistant": "**Approach:** use `asyncio.Queue` for coroutines or `queue.Queue` with locks for threads. Document invariants.",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["shard"]["domain"] == "computational_science"