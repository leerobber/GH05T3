"""GenomicSubstrate v1 + trading strategy lab tests."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.dna.omni_dna import OmniDNA
from oss.lab.trading_strategy import (
    run_old_stack_lab,
    run_oss_trading_lab,
    trading_lab_comparison,
)
from oss.schemas.genome import DNAType
from oss.substrate.genomic import (
    CapabilityDescriptor,
    get_genomic_substrate,
    query_genome,
    reset_genomic_substrate,
)
from oss.api.router import router as oss_router


def test_register_and_query_by_traits():
    reset_genomic_substrate()
    sub = get_genomic_substrate()
    dna = OmniDNA(registry_agent_id="TEST1", display_name="test-genome")
    dna.add_trait("math", 0.85)
    dna.add_trait("creativity", 0.75)
    gid = sub.register_genome(dna)
    hits = sub.query_by_traits({"math": 0.8, "creativity": 0.7})
    assert gid in hits


def test_query_by_capability_markets():
    reset_genomic_substrate()
    sub = get_genomic_substrate()
    dna = OmniDNA(registry_agent_id="AVERY", display_name="strategist")
    for t, v in (
        ("pattern_detection", 0.8),
        ("risk_tolerance", 0.7),
        ("market_intuition", 0.75),
        ("finance", 0.65),
        ("strategy", 0.72),
    ):
        dna.add_trait(t, v)
    dna.meta_dna["species_role"] = "investor"
    gid = sub.register_genome(dna)
    cap = CapabilityDescriptor(domain="markets", skill="strategy_design", min_level=0.7)
    hits = sub.query_by_capability(cap)
    assert gid in hits


def test_mutate_crossover_lineage_fitness():
    reset_genomic_substrate()
    sub = get_genomic_substrate()
    a = OmniDNA(registry_agent_id="PARENT_A", display_name="parent-a")
    b = OmniDNA(registry_agent_id="PARENT_B", display_name="parent-b")
    a.add_trait("pattern_detection", 0.6)
    b.add_trait("risk_tolerance", 0.7)
    id_a = sub.register_genome(a)
    id_b = sub.register_genome(b)
    before = sub.get_genome(id_a).traits["pattern_detection"].value
    sub.mutate(id_a, intensity=0.15)
    after = sub.get_genome(id_a).traits["pattern_detection"].value
    assert isinstance(after, float)
    sub.record_fitness(id_a, 0.82, {"task": "unit_test"})
    assert len(sub.fitness_history(id_a)) >= 1
    c1, c2 = sub.crossover(id_a, id_b)
    lineage = sub.get_lineage(c1.genome_id)
    assert id_a in lineage or c1.genome_id in lineage
    assert sub.count() >= 4


def test_spawn_agent_investor():
    reset_genomic_substrate()
    sub = get_genomic_substrate()
    sub.load_from_mind()
    ids = sub.query_by_role("investor")
    assert ids, "mind bootstrap should seed investor genome"
    handle = sub.spawn_agent(ids[0], "investor")
    assert handle.role == "investor"
    assert handle.genome_id == ids[0]
    assert handle.agent_id


def test_transmute():
    reset_genomic_substrate()
    sub = get_genomic_substrate()
    dna = OmniDNA(registry_agent_id="ALCHEMIST", display_name="transmute-test")
    dna.add_trait("base_metal", 0.9, DNAType.GENETIC)
    dna.transmutation_recipes = {("base_metal",): ("gold", 0.9)}
    gid = sub.register_genome(dna)
    ok = sub.transmute(gid, ["base_metal"])
    assert ok is True


def test_query_genome_backward_compat():
    segs = query_genome(capability="strategy_design", domain="markets")
    assert isinstance(segs, list)


def test_old_stack_lab():
    result = run_old_stack_lab(seed=7)
    assert result.strategy == "moving_average_crossover"
    assert "fast" in result.params


def test_oss_trading_lab_runs():
    reset_genomic_substrate()
    out = run_oss_trading_lab(seed=7, dry_run=True, generations=2)
    assert out["stack"] == "oss_genomic_substrate"
    assert out["generations"] == 2
    assert out["cycles"]
    assert out["final_best"].get("fitness_score") is not None


def test_trading_lab_comparison():
    reset_genomic_substrate()
    cmp = trading_lab_comparison(seed=7, dry_run=True)
    assert cmp["problem"]
    assert cmp["old_stack"]["stack"] == "old_files_classes_api"
    assert cmp["oss_stack"]["stack"] == "oss_genomic_substrate"
    assert "contrast" in cmp


def test_substrate_api_routes():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)
    assert client.get("/oss/substrate").status_code == 200
    assert client.get("/oss/substrate/genome?role=investor").status_code == 200
    assert client.get(
        "/oss/substrate/genome?domain=markets&skill=strategy_design&min_level=0.35"
    ).status_code == 200
    assert client.get("/oss/lab/trading?seed=7").status_code == 200