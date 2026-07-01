"""
SubstrateTransformer — convenience wrapper around SubstrateModel.

Provides a genome-aware entry point: given a genome_id (or AttentionConfig),
build the full model and expose encode() as the primary forward path.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from oss.substrate.attention_config import AttentionConfig
from oss.substrate.model import SubstrateConfig, SubstrateModel


class SubstrateTransformer:
    """
    Genome-tuned transformer built from MA_INBLAttention blocks.

    Typical usage:
        cfg = AttentionConfig.from_genome_traits(genome.traits, genome_id)
        model = SubstrateTransformer.from_attention_config(cfg)
        encoded, telemetry = model.encode(trait_vectors)
    """

    def __init__(self, model: SubstrateModel) -> None:
        self._model = model

    # ── factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_attention_config(
        cls,
        attn_cfg: AttentionConfig,
        *,
        num_layers: int = 2,
        ors_matrix: np.ndarray | None = None,
    ) -> "SubstrateTransformer":
        """Build a SubstrateTransformer tuned to a genome's AttentionConfig."""
        sub_cfg = SubstrateConfig.from_attention_config(
            attn_cfg,
            num_layers=num_layers,
            ors_matrix=ors_matrix,
        )
        return cls(SubstrateModel(sub_cfg))

    @classmethod
    def from_genome_traits(
        cls,
        traits: dict[str, float],
        genome_id: str = "",
        *,
        num_layers: int = 2,
    ) -> "SubstrateTransformer":
        """Build directly from a genome's trait dict."""
        attn_cfg = AttentionConfig.from_genome_traits(traits, genome_id=genome_id)
        return cls.from_attention_config(attn_cfg, num_layers=num_layers)

    # ── forward ───────────────────────────────────────────────────────────────

    def encode(
        self,
        x: np.ndarray,
    ) -> tuple[np.ndarray, list[dict[str, Any]]]:
        """
        Encode an input sequence through all transformer blocks.

        x       : [seq, embed_dim] float32
        Returns : (encoded, per_block_telemetry)
        """
        return self._model.forward(x)

    def score_candidates(
        self,
        query: np.ndarray,
        candidates: np.ndarray,
    ) -> np.ndarray:
        """
        Cosine affinity of each candidate against the query after encoding.

        query      : [embed_dim]
        candidates : [N, embed_dim]
        Returns    : [N] affinity scores in [0, 1]
        """
        seq = np.concatenate([query[None, :], candidates], axis=0)
        encoded, _ = self._model.forward(seq)
        q_enc = encoded[0]
        c_enc = encoded[1:]
        q_n = np.linalg.norm(q_enc) + 1e-8
        affinities = np.array([
            (float(np.dot(c, q_enc)) / (np.linalg.norm(c) + 1e-8) / q_n + 1.0) / 2.0
            for c in c_enc
        ], dtype=np.float32)
        return np.clip(affinities, 0.0, 1.0)

    # ── inspection ────────────────────────────────────────────────────────────

    @property
    def config(self) -> SubstrateConfig:
        return self._model.cfg

    @property
    def embed_dim(self) -> int:
        return self._model.embed_dim

    @property
    def num_layers(self) -> int:
        return self._model.num_layers

    def attention_modules(self):
        """Yield (layer_idx, MA_INBLAttention) for each block."""
        return self._model.attention_modules()
