"""
Genome-driven linguistic specialisation.

Maps KernelGenome hyperparameters to a LinguisticTraits struct that
describes the genome's conversational posture.  Used by DeployManager
and SentinelPrime to route requests to the best-fitting genome.
"""
from __future__ import annotations

from dataclasses import dataclass

from oss.living_loop.genome import KernelGenome


@dataclass
class LinguisticTraits:
    technical_bias: float = 0.5    # low entropy → precise, structured
    casual_bias: float = 0.5       # high temperature → relaxed, varied
    precision_bias: float = 0.5    # low max_growth → conservative residual
    loyalty_bias: float = 0.5      # high training_binary_ratio → stable
    innovation_bias: float = 0.5   # high max_growth → exploratory residual
    binary_code_influence: float = 0.3  # weight given to binary cluster codes


def genome_to_linguistic_traits(genome: KernelGenome) -> LinguisticTraits:
    """
    Derive LinguisticTraits from a KernelGenome's attention hyperparameters.

    Mappings (all clipped to [0, 1]):
      technical_bias  ← 1 - temperature / 10       (sharp → technical)
      casual_bias     ← temperature / 10            (warm → casual)
      precision_bias  ← 1 - max_growth / 2          (tight → precise)
      loyalty_bias    ← training_binary_ratio        (direct carry-over)
      innovation_bias ← max_growth                  (growth → innovation)
    """
    def _clip(v: float) -> float:
        return max(0.0, min(1.0, v))

    ors_variant = getattr(genome, "ors_variant", "qr")
    # QR / block_qr ORS variants produce tighter, more structured embeddings
    binary_influence = 0.1 if ors_variant in ("qr", "block_qr") else 0.3

    return LinguisticTraits(
        technical_bias=_clip(1.0 - genome.temperature / 10.0),
        casual_bias=_clip(genome.temperature / 10.0),
        precision_bias=_clip(1.0 - genome.max_growth / 2.0),
        loyalty_bias=_clip(genome.training_binary_ratio),
        innovation_bias=_clip(genome.max_growth),
        binary_code_influence=binary_influence,
    )


def dominant_mode(traits: LinguisticTraits) -> str:
    """
    Return the conversation mode name most aligned with these traits.

    Maps to the ConversationModes built-in vocabulary.
    """
    scores = {
        "technical":    traits.technical_bias + traits.precision_bias,
        "exploratory":  traits.casual_bias + traits.innovation_bias,
        "loyal_stable": traits.loyalty_bias + traits.precision_bias,
        "innovative":   traits.innovation_bias + (1.0 - traits.loyalty_bias),
    }
    return max(scores, key=lambda k: scores[k])
