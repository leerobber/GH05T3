"""OSS Sprint 3 — Omega rewrite, DDRS, holographic memory."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.dna.omega_rewrite import OmegaRewriter, REWRITE_THRESHOLD
from oss.dna.omni_dna import OmniDNA
from oss.economy.desire import DesireSystem, DesireType
from oss.mind.holographic import HolographicMemory
from oss.schemas.genome import Trait


@pytest.fixture
def rewriter(tmp_path, monkeypatch):
    monkeypatch.setattr("oss.dna.omega_rewrite._MANIFEST_DIR", tmp_path / "manifests")
    return OmegaRewriter(threshold=REWRITE_THRESHOLD)


@pytest.fixture
def ddrs(tmp_path, monkeypatch):
    backend = _ROOT / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    db = tmp_path / "palace.db"
    monkeypatch.setenv("ECONOMY_DB_PATH", str(db))
    monkeypatch.setenv("MARKETPLACE_DB_PATH", str(db))
    import economy.ledger as ledger_mod
    ledger_mod._DB_PATH = db
    ledger_mod._ledger = None
    import oss.economy.neuro_coin as nc_mod
    nc_mod._neuro = None
    return DesireSystem()


def test_omega_rewrite_below_threshold(rewriter):
    dna = OmniDNA(traits={"coding": Trait("coding", 0.7)}, registry_agent_id="FORGE")
    result = rewriter.rewrite_if_elite(dna, score=0.5)
    assert result["rewritten"] is False


def test_omega_rewrite_elite_applies_patches(rewriter):
    dna = OmniDNA(
        traits={"coding": Trait("coding", 0.75), "math": Trait("math", 0.8)},
        registry_agent_id="FORGE",
    )
    result = rewriter.rewrite_if_elite(dna, score=0.9)
    assert result["rewritten"] is True
    assert dna.traits["coding"].value > 0.75
    assert any(e.get("event") == "omega_rewrite" for e in dna.evolution_history)
    assert Path(result["manifest_path"]).is_file()


def test_ddrs_top_desire_and_fulfillment(ddrs):
    ddrs.add_desire("FORGE", DesireType.SKILL, "master Rust", priority=2.0)
    ddrs.add_desire("FORGE", DesireType.KNOWLEDGE, "read papers", priority=0.5)
    top = ddrs.get_top_desire("FORGE")
    assert top is not None
    assert top.desire_type == DesireType.SKILL

    out = ddrs.reward_agent("FORGE", {"tags": ["CODEX"], "coding": True, "reward": 20})
    assert out["mode"] == "ddrs"
    assert out["neuro_coin_reward"] > 0
    assert top.fulfillment > 0


def test_ddrs_flat_reward_without_desires(ddrs):
    out = ddrs.reward_agent("NEXUS", {"reward": 15, "reason": "ops"})
    assert out["mode"] == "flat"
    assert out["neuro_coin_reward"] == 15


def test_holographic_shard_and_reconstruct():
    holo = HolographicMemory()
    memory = {"type": "task", "problem": "reduce latency", "agent": "FORGE"}
    shards = holo.shard_memory("forge-abc", memory, shard_count=4)
    assert len(shards) == 4

    rebuilt = holo.reconstruct("forge-abc", min_shards=1)
    assert len(rebuilt) >= 1
    assert rebuilt[0].get("problem") == "reduce latency"

    qualia = holo.qualia_from_shards("forge-abc")
    assert "curiosity" in qualia
    assert qualia["curiosity"] > 0