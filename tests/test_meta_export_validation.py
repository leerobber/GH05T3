"""Meta-export schema validation — Phase 1 gate."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.oss.meta_export import validate_meta_sample, validate_genomic_sample


def test_validate_meta_sample_ok():
    sample = {
        "genome_id": "DNA-001",
        "role": "SCIENTIST",
        "traits": {"creativity": 0.7},
        "fitness_history": [0.6, 0.7],
        "neurocoins": 10.0,
        "recent_memories": [],
    }
    ok, errs = validate_meta_sample(sample)
    assert ok, errs


def test_validate_meta_sample_rejects_bad_traits():
    sample = {
        "genome_id": "DNA-001",
        "role": "SCIENTIST",
        "traits": {"creativity": 1.5},
        "fitness_history": [],
        "neurocoins": 0,
        "recent_memories": [],
    }
    ok, errs = validate_meta_sample(sample)
    assert not ok
    assert any("trait" in e for e in errs)


def test_validate_genomic_sample_ok():
    sample = {
        "agent_id": "oracle",
        "generation": 3,
        "fitness_ema": 0.65,
        "loyalty_level": "novice",
        "genome_snapshot": {"loci": {"cognitive": {"score": 0.5, "molecules": {}}}},
    }
    ok, errs = validate_genomic_sample(sample)
    assert ok, errs