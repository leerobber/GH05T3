"""
AttentionDomainScorer — MA-INBL attention over genome trait vectors.

Used by the inference router and training bridge to compute attention-weighted
fitness scores for candidate strands.  Runs on the numpy backend (no GPU needed).
"""
from __future__ import annotations

from typing import Any

import numpy as np

from oss.attention.kernel import TRITON_AVAILABLE
from oss.substrate.attention_config import (
    CANONICAL_TRAITS,
    TRAIT_DIM,
    AttentionConfig,
    traits_to_vector,
)

# Domain → canonical trait indices that define competence in that domain
_DOMAIN_TRAIT_WEIGHTS: dict[str, dict[str, float]] = {
    "deep_learning_architectures": {
        "coding": 0.9, "research": 0.8, "math": 0.8, "analysis": 0.7,
        "innovation": 0.6, "reasoning": 0.7,
    },
    "machine_learning_theory": {
        "math": 0.9, "research": 0.9, "analysis": 0.8, "reasoning": 0.8,
        "curiosity": 0.6,
    },
    "genomics_inspired_ai": {
        "research": 0.9, "curiosity": 0.8, "innovation": 0.8,
        "analysis": 0.7, "math": 0.6,
    },
    "agentic_systems_science": {
        "coding": 0.9, "systems": 0.9, "strategy": 0.8, "ops": 0.7,
        "leadership": 0.6, "reasoning": 0.7,
    },
    "alignment_and_safety_science": {
        "safety": 0.9, "ethics": 0.9, "audit": 0.8, "compliance": 0.7,
        "reasoning": 0.8, "analysis": 0.7,
    },
    "markets": {
        "finance": 0.9, "strategy": 0.8, "risk": 0.8, "market_intuition": 0.9,
        "pattern_detection": 0.7, "economics": 0.8,
    },
    "general_cognition": {
        "general": 0.8, "reasoning": 0.8, "communication": 0.7,
        "adaptability": 0.7, "self_reflection": 0.6,
    },
}


def domain_trait_vector(domain: str) -> np.ndarray:
    """Build the canonical trait vector for a forge domain."""
    weights = _DOMAIN_TRAIT_WEIGHTS.get(domain, _DOMAIN_TRAIT_WEIGHTS["general_cognition"])
    return traits_to_vector(weights)


class TraitVectorEncoder:
    """
    Encodes a sequence of trait dicts into a [seq_len, TRAIT_DIM] float32 array.

    Used to prepare input for MA_INBLAttention.
    """

    def __init__(self, trait_keys: list[str] | None = None) -> None:
        self._keys = trait_keys or CANONICAL_TRAITS

    def encode_one(self, traits: dict[str, float]) -> np.ndarray:
        return traits_to_vector(traits)

    def encode_batch(self, trait_dicts: list[dict[str, float]]) -> np.ndarray:
        """Returns [N, TRAIT_DIM] float32."""
        return np.stack([self.encode_one(t) for t in trait_dicts], axis=0)


class AttentionDomainScorer:
    """
    Scores a list of genome trait dicts against a query domain using MA-INBL attention.

    The query is encoded as a single trait vector (from domain_trait_vector).
    Candidates are the trait vectors of the genomes under evaluation.
    Attention selects the candidates most relevant to the query domain.

    Returns per-candidate scores in [0, 1] derived from attention weights × fitness.
    """

    def __init__(
        self,
        *,
        embed_dim: int = TRAIT_DIM,
        num_heads: int = 4,
        temperature: float = 0.5,
        max_growth: float = 0.3,
        seed: int = 0,
        backend: str = "auto",
    ) -> None:
        from oss.attention.attention import MA_INBLAttention
        # If Triton is available and backend="auto", use it; else numpy
        resolved_backend = "triton" if (TRITON_AVAILABLE and backend in ("auto", "triton")) else "numpy"
        self._attn = MA_INBLAttention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            temperature=temperature,
            max_growth=max_growth,
            seed=seed,
            backend=resolved_backend,
        )
        self._encoder = TraitVectorEncoder()

    def score(
        self,
        domain: str,
        candidate_traits: list[dict[str, float]],
        candidate_fitness: list[float] | None = None,
        *,
        log_telemetry: bool = True,
    ) -> list[float]:
        """
        Score each candidate genome's relevance to the given forge domain.

        domain            : forge domain key (e.g. "deep_learning_architectures")
        candidate_traits  : list of trait dicts (one per genome)
        candidate_fitness : optional prior fitness scores (blended into result)
        Returns           : list of [0, 1] affinity scores, same length as candidates
        """
        if not candidate_traits:
            return []

        query_vec = domain_trait_vector(domain)                    # [TRAIT_DIM]
        cand_mat  = self._encoder.encode_batch(candidate_traits)   # [N, TRAIT_DIM]

        # Prepend query as the first "token"; run attention over [N+1, TRAIT_DIM]
        seq = np.concatenate([query_vec[None, :], cand_mat], axis=0)  # [N+1, D]
        out, tel = self._attn.forward(seq)

        if log_telemetry:
            self._write_telemetry(tel, domain=domain, n_candidates=len(candidate_traits))

        # Output[1:] are the attended candidate representations
        attended = out[1:]                                          # [N, D]
        # Cosine similarity between attended candidates and query output
        q_out  = out[0]                                            # [D]
        q_norm = np.linalg.norm(q_out) + 1e-8
        scores = []
        for i, a in enumerate(attended):
            a_norm = np.linalg.norm(a) + 1e-8
            cos_sim = float(np.dot(a, q_out) / (a_norm * q_norm))
            affinity = (cos_sim + 1.0) / 2.0                      # map [-1,1] → [0,1]
            if candidate_fitness:
                fit = float(candidate_fitness[i])
                affinity = 0.6 * affinity + 0.4 * fit
            scores.append(round(float(np.clip(affinity, 0.0, 1.0)), 4))
        return scores

    def rank(
        self,
        domain: str,
        candidate_traits: list[dict[str, float]],
        candidate_fitness: list[float] | None = None,
    ) -> list[int]:
        """Return indices sorted by descending attention-weighted affinity score."""
        scores = self.score(domain, candidate_traits, candidate_fitness, log_telemetry=False)
        return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    def _write_telemetry(self, tel: dict, domain: str, n_candidates: int) -> None:
        try:
            from oss.attention.telemetry import AttentionTelemetrySink
            sink = AttentionTelemetrySink()
            sink.log(
                {
                    "mean_mag_x": tel.get("x_mag_mean", 0.0),
                    "mean_candidate_mag": tel.get("cand_mag_mean", 0.0),
                    "mean_mgc_scale": tel.get("mgc_scale_mean", 1.0),
                },
                agent_id=f"scorer:{domain}",
            )
        except Exception:
            pass   # telemetry is best-effort


_scorer: AttentionDomainScorer | None = None


def get_scorer(seed: int = 42) -> AttentionDomainScorer:
    """Return the shared singleton scorer (lazy-initialised)."""
    global _scorer
    if _scorer is None:
        _scorer = AttentionDomainScorer(seed=seed)
    return _scorer


def score_strands_for_domain(
    domain: str,
    strands: list[dict[str, Any]],
) -> list[tuple[float, dict[str, Any]]]:
    """
    Convenience: score a list of raw strand dicts for a given domain.

    Each strand dict should have "traits" and optionally "fitness" keys.
    Returns list of (attention_score, strand) sorted descending.
    """
    scorer = get_scorer()
    trait_dicts = [s.get("traits") or {} for s in strands]
    fitness_vals = [float(s.get("fitness", 0.5)) for s in strands]
    scores = scorer.score(domain, trait_dicts, fitness_vals, log_telemetry=False)
    ranked = sorted(zip(scores, strands), key=lambda x: x[0], reverse=True)
    return ranked
