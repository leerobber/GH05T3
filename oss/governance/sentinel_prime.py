"""
SentinelPrime — Phase 5 meta-governance layer.

Evaluates genomes across six axes and makes strict deployment decisions:
  "active"  — elite, must pass all thresholds
  "canary"  — promising but not yet fully proven
  "retired" — unstable, low-quality, or regressing
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class GenomeScores:
    loyalty: float          # stability, entropy control
    intelligence: float     # trait alignment, attention quality
    innovation: float       # fitness improvement, novelty
    genetic_quality: float  # parameter coherence
    resilience: float       # backend parity, robustness
    long_horizon: float     # trajectory of improvement

    def as_dict(self) -> Dict[str, float]:
        return {
            "loyalty": self.loyalty,
            "intelligence": self.intelligence,
            "innovation": self.innovation,
            "genetic_quality": self.genetic_quality,
            "resilience": self.resilience,
            "long_horizon": self.long_horizon,
        }


class SentinelPrime:
    """
    SentinelPrime evaluates genomes on six axes and decides their deployment status.

    Decisions are intentionally strict — a genome must demonstrate sustained
    excellence across all axes to reach "active" status.
    """

    def __init__(self, consistency_window: int = 5) -> None:
        self.consistency_window = consistency_window
        self.history: Dict[str, List[GenomeScores]] = {}

    # ── scoring ──────────────────────────────────────────────────────────────

    def score_genome(self, genome_id: str, telemetry: Dict[str, Any]) -> GenomeScores:
        """
        Derive six-axis scores from a telemetry dict.

        Standard keys used (all optional — missing keys use safe defaults):
          mean_mgc_scale, mean_attn_entropy, output_norm,
          trait_alignment, fitness_delta, genetic_coherence,
          backend_parity, trajectory
        """
        def _f(key: str, default: float) -> float:
            return float(telemetry.get(key, default))

        def _clamp(x: float) -> float:
            return max(0.0, min(1.0, x))

        loyalty        = _clamp(_f("mean_mgc_scale", 1.0) - 0.2 * _f("mean_attn_entropy", 0.0))
        intelligence   = _clamp(_f("trait_alignment", 0.5))
        innovation     = _clamp(_f("fitness_delta", 0.0))
        genetic_quality = _clamp(_f("genetic_coherence", 0.5))
        resilience     = _clamp(_f("backend_parity", 0.5))
        long_horizon   = _clamp(_f("trajectory", 0.5))

        return GenomeScores(
            loyalty=loyalty,
            intelligence=intelligence,
            innovation=innovation,
            genetic_quality=genetic_quality,
            resilience=resilience,
            long_horizon=long_horizon,
        )

    def record(self, genome_id: str, scores: GenomeScores) -> None:
        """Append scores to the sliding consistency window."""
        window = self.history.setdefault(genome_id, [])
        window.append(scores)
        if len(window) > self.consistency_window:
            window.pop(0)

    def _average_scores(self, genome_id: str) -> GenomeScores | None:
        window = self.history.get(genome_id, [])
        if not window:
            return None
        n = len(window)
        return GenomeScores(
            loyalty=sum(s.loyalty for s in window) / n,
            intelligence=sum(s.intelligence for s in window) / n,
            innovation=sum(s.innovation for s in window) / n,
            genetic_quality=sum(s.genetic_quality for s in window) / n,
            resilience=sum(s.resilience for s in window) / n,
            long_horizon=sum(s.long_horizon for s in window) / n,
        )

    # ── decision ─────────────────────────────────────────────────────────────

    def decide(self, genome_id: str) -> str:
        """
        Return "active", "canary", or "retired" for a genome.

        Active thresholds (strict):
          loyalty ≥ 0.85, intelligence ≥ 0.80, innovation ≥ 0.75,
          genetic_quality ≥ 0.80, resilience ≥ 0.70, long_horizon ≥ 0.75

        Canary thresholds (decent but unproven):
          loyalty ≥ 0.60, intelligence ≥ 0.55, innovation ≥ 0.50,
          genetic_quality ≥ 0.60

        Everything else: "retired".
        """
        avg = self._average_scores(genome_id)
        if avg is None:
            return "retired"

        if (
            avg.loyalty >= 0.85
            and avg.intelligence >= 0.80
            and avg.innovation >= 0.75
            and avg.genetic_quality >= 0.80
            and avg.resilience >= 0.70
            and avg.long_horizon >= 0.75
        ):
            return "active"

        if (
            avg.loyalty >= 0.60
            and avg.intelligence >= 0.55
            and avg.innovation >= 0.50
            and avg.genetic_quality >= 0.60
        ):
            return "canary"

        return "retired"

    def status_summary(self) -> Dict[str, str]:
        """Return current decision for every tracked genome."""
        return {gid: self.decide(gid) for gid in self.history}
