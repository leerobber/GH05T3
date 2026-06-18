"""OSS Omni-DNA unit tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.dna.omni_dna import OmniDNA
from oss.dna.store import GenomeStore
from oss.schemas.genome import DNAType, Trait


def test_omni_dna_evolve_changes_traits():
    dna = OmniDNA(
        registry_agent_id="TEST",
        traits={"coding": Trait("coding", 0.5)},
    )
    before = dna.traits["coding"].value
    deltas = dna.evolve(score=0.9)
    assert dna.traits["coding"].value != before or deltas == {}


def test_omni_dna_unique_id_stable():
    dna = OmniDNA(
        registry_agent_id="FORGE",
        traits={"coding": Trait("coding", 0.8)},
    )
    assert dna.unique_id.startswith("forge-")


def test_genome_store_seed_and_roundtrip(tmp_path):
    store = GenomeStore(db_path=tmp_path / "test_genomes.db")
    store.seed_specialists()
    records = store.list_all()
    assert len(records) >= 6
    first = records[0]
    loaded = store.get(first.genome_id)
    assert loaded is not None
    assert loaded.registry_agent_id == first.registry_agent_id


def test_transmute_traits():
    dna = OmniDNA(
        traits={
            "math": Trait("math", 0.7),
            "physics": Trait("physics", 0.6),
        },
        transmutation_recipes={("math", "physics"): ("quantum_physics", 0.9)},
    )
    assert dna.transmute_traits(["math", "physics"]) is True
    assert "quantum_physics" in dna.traits
    assert dna.traits["quantum_physics"].dna_type == DNAType.ALCHEMICAL