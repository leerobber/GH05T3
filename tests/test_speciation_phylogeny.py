"""Phylogeny ASCII rendering from speciation events."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "backend"))

from backend.oss.speciation import SpeciationEvent, render_phylogeny_ascii


def test_render_phylogeny_measured_divergence():
    events = [
        SpeciationEvent(
            timestamp=1.0,
            parent_species="ROOT",
            new_species="SPECIES-001-1234",
            divergence=0.142,
            trigger="high_pairwise_divergence",
            niche="alignment",
        ),
        SpeciationEvent(
            timestamp=2.0,
            parent_species="ROOT",
            new_species="SPECIES-002-5678",
            divergence=0.158,
            trigger="high_pairwise_divergence",
            niche="volatility",
        ),
    ]
    tree = render_phylogeny_ascii(events)
    assert tree.startswith("ROOT")
    assert "SPECIES-001-1234" in tree
    assert "divergence=0.14" in tree
    assert "SPECIES-002-5678" in tree


def test_render_phylogeny_empty():
    assert "(no speciation events yet)" in render_phylogeny_ascii([])