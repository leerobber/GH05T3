"""
Per-genome MA-INBL attention configuration for the Genomic Substrate.

AttentionConfig stores the hyperparameters needed to build an MA_INBLAttention
module tuned to a specific genome's trait profile.  It is derived automatically
from genome trait values and serialises alongside GenomeSegment records.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np

# ── Canonical trait vocabulary (32 traits — 1 uint32 word for bit-packing) ────

CANONICAL_TRAITS: list[str] = [
    "coding",            "research",          "analysis",          "math",
    "curiosity",         "pattern_detection", "risk_tolerance",    "market_intuition",
    "finance",           "strategy",          "risk",              "ops",
    "systems",           "reliability",       "safety",            "ethics",
    "audit",             "compliance",        "design",            "growth",
    "monetization",      "ux",                "creativity",        "empathy",
    "innovation",        "economics",         "self_reflection",   "communication",
    "reasoning",         "adaptability",      "leadership",        "general",
]

TRAIT_DIM: int = len(CANONICAL_TRAITS)          # 32
assert TRAIT_DIM == 32, "CANONICAL_TRAITS must stay at 32 for single-word bit packing"


def traits_to_vector(traits: dict[str, float]) -> np.ndarray:
    """
    Encode a genome trait dict as a fixed-size float32 vector.

    Missing traits default to 0.5 (neutral baseline).
    Returns shape [TRAIT_DIM] = [32].
    """
    vec = np.full(TRAIT_DIM, 0.5, dtype=np.float32)
    for i, name in enumerate(CANONICAL_TRAITS):
        if name in traits:
            vec[i] = float(np.clip(traits[name], 0.0, 1.0))
    return vec


# ── AttentionConfig ────────────────────────────────────────────────────────────

@dataclass
class AttentionConfig:
    """
    MA-INBL attention hyperparameters for a single genome.

    Stored on GenomeSegment so training and inference pipelines can build a
    deterministic MA_INBLAttention module for each genome without global state.
    """

    embed_dim: int = TRAIT_DIM          # = 32 (trait vector length)
    num_heads: int = 4                  # head_dim = 8
    binary_ratio: float = 0.0          # 0 → dual-scale inactive (safe default)
    training_binary_ratio: float = 1.0
    temperature: float = 1.0
    max_growth: float = 0.5
    seed: int = 0                       # derived from genome_id for determinism
    backend: str = "auto"              # "auto" | "numpy" | "triton"

    # ── derived ──────────────────────────────────────────────────────────────

    def build_module(self, backend: str | None = None):  # type: ignore[return]
        """
        Construct a ready-to-use MA_INBLAttention from this config.

        backend : override the config's backend field ("auto" | "numpy" | "triton").
        When a genome trait-derived config requests "triton" but Triton is not
        installed, the preference falls back to "auto" (numpy) automatically.
        """
        from oss.attention.attention import MA_INBLAttention
        from oss.attention.kernel import TRITON_AVAILABLE
        resolved = backend if backend is not None else self.backend
        # Treat genome-preference "triton" as "auto" when GPU is not available
        if resolved == "triton" and not TRITON_AVAILABLE:
            resolved = "auto"
        return MA_INBLAttention(
            embed_dim=self.embed_dim,
            num_heads=self.num_heads,
            binary_ratio=self.binary_ratio,
            training_binary_ratio=self.training_binary_ratio,
            temperature=self.temperature,
            max_growth=self.max_growth,
            seed=self.seed,
            backend=resolved,
        )

    # ── serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "embed_dim": self.embed_dim,
            "num_heads": self.num_heads,
            "binary_ratio": self.binary_ratio,
            "training_binary_ratio": self.training_binary_ratio,
            "temperature": self.temperature,
            "max_growth": self.max_growth,
            "seed": self.seed,
            "backend": self.backend,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AttentionConfig":
        return cls(
            embed_dim=int(d.get("embed_dim", TRAIT_DIM)),
            num_heads=int(d.get("num_heads", 4)),
            binary_ratio=float(d.get("binary_ratio", 0.0)),
            training_binary_ratio=float(d.get("training_binary_ratio", 1.0)),
            temperature=float(d.get("temperature", 1.0)),
            max_growth=float(d.get("max_growth", 0.5)),
            seed=int(d.get("seed", 0)),
            backend=str(d.get("backend", "auto")),
        )

    # ── factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_genome_traits(
        cls,
        traits: dict[str, float],
        genome_id: str = "",
    ) -> "AttentionConfig":
        """
        Derive an AttentionConfig from a genome's trait values.

        Mapping:
          temperature           ← 1.0 - 0.6 * analysis  (sharper for analytical genomes)
          max_growth            ← 0.2 + 0.6 * risk_tolerance
          training_binary_ratio ← 0.7 + 0.3 * reliability
          backend               ← "triton" when compute_intensity > 0.7, else "auto"
          seed                  ← first 8 hex digits of sha256(genome_id)
        """
        analysis     = float(traits.get("analysis", 0.5))
        risk_tol     = float(traits.get("risk_tolerance", 0.5))
        reliability  = float(traits.get("reliability", 0.5))
        # High coding/systems traits → prefer GPU (Triton) backend when available
        compute      = float(traits.get("coding", traits.get("systems", 0.5)))

        temperature  = max(0.2, 1.0 - 0.6 * analysis)
        max_growth   = 0.2 + 0.6 * risk_tol
        tbr          = 0.7 + 0.3 * reliability
        backend      = "triton" if compute > 0.7 else "auto"

        seed = 0
        if genome_id:
            digest = hashlib.sha256(genome_id.encode()).hexdigest()
            seed = int(digest[:8], 16) % (2 ** 31)

        return cls(
            embed_dim=TRAIT_DIM,
            num_heads=4,
            binary_ratio=0.0,
            training_binary_ratio=round(tbr, 4),
            temperature=round(temperature, 4),
            max_growth=round(max_growth, 4),
            seed=seed,
            backend=backend,
        )

    @classmethod
    def default(cls) -> "AttentionConfig":
        return cls()
