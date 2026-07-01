"""Loyalty-gated proposal system."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.oss.genomic.loyalty import LoyaltySystem, LoyaltyLevel


def test_novice_cannot_propose():
    ls = LoyaltySystem()
    ok, msg = ls.propose_change("oracle", "new_molecule", evidence={"cycles": 1})
    assert not ok
    assert "novice" in msg.lower()


def test_hyper_elite_can_propose_molecule():
    ls = LoyaltySystem()
    for _ in range(20):
        ls.record("oracle", [0.9, 0.92, 0.91, 0.93], user_rating=0.95)
    assert ls.get_level("oracle").value_score >= LoyaltyLevel.HYPER_ELITE.value_score
    ok, pid = ls.propose_change(
        "oracle",
        "new_molecule",
        molecule="M_ADAPTIVE_RECOVERY",
        locus="cognitive",
        evidence={"theory_lab_cycles": 3, "mean_fitness": 0.72},
    )
    assert ok, pid
    assert pid.startswith("prop_")
    assert len(ls.list_proposals("oracle")) == 1