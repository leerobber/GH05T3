"""MVS core integration tests — Phase 1 gate (backend/oss RNA layer)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _reset_mvs_singletons():
    import backend.oss.mvs as mvs_mod
    import backend.oss.genomic_substrate as sub_mod

    mvs_mod._mvs = None
    sub_mod._substrate = None


@pytest.fixture
def isolated_mvs(tmp_path, monkeypatch):
    """Fresh MVS stack with no disk persistence."""
    _reset_mvs_singletons()
    monkeypatch.setenv("GENOMES_PATH", str(tmp_path / "oss_genomes.json"))
    from backend.oss.genomic_substrate import GenomicSubstrate

    monkeypatch.setattr("backend.oss.genomic_substrate.GENOMES_PATH", tmp_path / "oss_genomes.json")
    sub = GenomicSubstrate(persist=False)
    from backend.oss.omni_mind import OmniMind
    from backend.oss.omni_economy import OmniEconomy

    return {"substrate": sub, "mind": OmniMind(sub), "economy": OmniEconomy()}


def test_omni_dna_evolve_deterministic_with_seed():
    from backend.oss.omni_dna import OmniDNA

    a = OmniDNA("DNA-TEST-001", "SCIENTIST", seed=42)
    b = OmniDNA("DNA-TEST-002", "SCIENTIST", seed=42)
    before_a = dict(a.traits)
    before_b = dict(b.traits)

    events_a = a.evolve(strength=0.1, reason="test")
    events_b = b.evolve(strength=0.1, reason="test")

    assert a.traits == b.traits
    assert [e.trait for e in events_a] == [e.trait for e in events_b]
    assert before_a != a.traits or not events_a


def test_register_genome_validation(isolated_mvs):
    sub = isolated_mvs["substrate"]
    from backend.oss.omni_dna import OmniDNA, create_omnidna

    dna = create_omnidna("BUILDER", seed=7)
    gid = sub.register_genome(dna)
    assert gid == dna.genome_id
    assert gid in sub.genomes

    with pytest.raises(TypeError):
        sub.register_genome("not-dna")  # type: ignore[arg-type]

    bad = OmniDNA("", "BUILDER")
    with pytest.raises(ValueError, match="genome_id"):
        sub.register_genome(bad)

    empty_traits = OmniDNA("DNA-EMPTY", "BUILDER", traits={})
    # OmniDNA fills UNIVERSAL_TRAITS even when passed {}; registration should succeed.
    assert sub.register_genome(empty_traits) == "DNA-EMPTY"


def test_register_genome_idempotent(isolated_mvs):
    sub = isolated_mvs["substrate"]
    from backend.oss.omni_dna import create_omnidna

    dna = create_omnidna("OPERATOR", seed=3)
    first = sub.register_genome(dna)
    second = sub.register_genome(dna)
    assert first == second
    assert len(sub.genomes) == 1


def test_omni_mind_sync_no_error(isolated_mvs):
    sub = isolated_mvs["substrate"]
    mind = isolated_mvs["mind"]
    from backend.oss.omni_dna import create_omnidna

    dna = create_omnidna("THEORIST_ELITE", seed=11)
    dna.add_memory({"type": "test", "canonical": True, "computed_score": 0.9})
    gid = sub.register_genome(dna, role="THEORIST_ELITE")
    handle = sub.spawn_agent(gid)
    handle.act({"prompt": "Sync probe task", "summary": "probe"})

    count = mind.sync()
    assert count >= 1
    assert mind.state.shared_memory


def test_omni_economy_reward_ledger_consistency(isolated_mvs, monkeypatch):
    econ = isolated_mvs["economy"]
    agent = "DNA-ECON-001"

    # Force in-memory ledger path for deterministic unit test (no external DB).
    def _no_db(*_args, **_kwargs):
        raise RuntimeError("no db")

    monkeypatch.setattr("backend.oss.omni_economy.credit", _no_db)
    monkeypatch.setattr("backend.oss.omni_economy.balance", _no_db)

    econ.reward(agent, 50.0, reason="unit_test")
    econ.reward(agent, 25.0, reason="unit_test")
    assert econ.get_balance(agent) == 75.0

    assert econ.transfer(agent, "DNA-ECON-002", 20.0, reason="collab")
    assert econ.get_balance(agent) == 55.0
    assert econ.get_balance("DNA-ECON-002") == 20.0


def test_agent_handle_act_graceful_on_llm_failure(isolated_mvs):
    sub = isolated_mvs["substrate"]
    from backend.oss.omni_dna import create_omnidna

    dna = create_omnidna("THEORIST_ELITE", seed=99)
    gid = sub.register_genome(dna, role="THEORIST_ELITE")
    handle = sub.spawn_agent(gid)

    with patch("backend.ghost_llm._call_gh05t3", side_effect=RuntimeError("llm down")):
        result = handle.act({"prompt": "Model volatility regimes", "summary": "theory"})

    assert result["agent_id"] == gid
    assert result.get("fallback") is True
    assert result["raw_output"]
    assert any(m.get("type") == "act" for m in dna.phenomenal_memory)


def test_agent_handle_act_graceful_on_conditioning_error(isolated_mvs):
    sub = isolated_mvs["substrate"]
    from backend.oss.omni_dna import create_omnidna

    dna = create_omnidna("BUILDER", seed=5)
    gid = sub.register_genome(dna)
    handle = sub.spawn_agent(gid)

    with patch.object(handle, "condition_task_with_dna", side_effect=ValueError("bad task")):
        result = handle.act({"prompt": "broken"})

    assert result["fallback"] is True
    assert "error" in result
    assert any(m.get("type") == "error" for m in dna.phenomenal_memory)


def test_mvs_get_mvs_wires_layers(monkeypatch, tmp_path):
    _reset_mvs_singletons()
    monkeypatch.setattr("backend.oss.genomic_substrate.GENOMES_PATH", tmp_path / "oss_genomes.json")

    from backend.oss.mvs import get_mvs

    mvs = get_mvs()
    assert "substrate" in mvs
    assert "mind" in mvs
    assert "economy" in mvs
    assert hasattr(mvs["substrate"], "register_genome")
    assert hasattr(mvs["mind"], "sync")


def test_meta_export_collects_registered_genomes(isolated_mvs):
    sub = isolated_mvs["substrate"]
    econ = isolated_mvs["economy"]
    mind = isolated_mvs["mind"]
    from backend.oss.omni_dna import create_omnidna
    from backend.oss.meta_export import collect_meta_samples

    dna = create_omnidna("SCIENTIST", seed=1)
    gid = sub.register_genome(dna)
    econ.reward(gid, 10.0, reason="export_test")

    samples = collect_meta_samples(sub, mind, econ)
    assert any(s["genome_id"] == gid for s in samples)
    assert all("traits" in s and s["traits"] for s in samples)