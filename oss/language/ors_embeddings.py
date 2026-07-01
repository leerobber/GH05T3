"""
ORS-rotated language embeddings.

Applies per-head orthogonal rotations to base token embeddings so each
MA-INBL attention head sees a geometrically distinct view of the embedding
space.  ORS variants are driven by KernelGenome.ors_variant.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np

from oss.living_loop.experiments import _build_ors_variant
from oss.living_loop.genome import KernelGenome


@dataclass
class ORSEmbeddingConfig:
    num_heads: int = 4
    embed_dim: int = 32


class ORSEmbeddings:
    """
    Builds and caches per-head ORS-rotated embedding matrices.

    Usage:
        oe = ORSEmbeddings(base_embeddings)
        oe.build_for_genome(genome)
        head_emb = oe.head_embeddings(head_id)   # [V, head_dim]
    """

    def __init__(
        self,
        base_embeddings: np.ndarray,
        cfg: ORSEmbeddingConfig | None = None,
    ) -> None:
        self.cfg = cfg or ORSEmbeddingConfig(embed_dim=base_embeddings.shape[-1])
        self.base = base_embeddings.astype(np.float32)
        self.rotated: Dict[int, np.ndarray] = {}
        self._head_dim = self.cfg.embed_dim // self.cfg.num_heads

    def build_for_genome(self, genome: KernelGenome) -> None:
        """
        Compute per-head rotated views from the genome's ORS variant.

        Stores results in self.rotated[head_id] → [V, head_dim].
        """
        ors = _build_ors_variant(
            variant=genome.ors_variant,
            embed_dim=self.cfg.embed_dim,
            num_heads=self.cfg.num_heads,
            head_dim=self._head_dim,
        )  # [num_heads, head_dim, head_dim]

        self.rotated.clear()
        for h in range(self.cfg.num_heads):
            s = h * self._head_dim
            head_slice = self.base[:, s : s + self._head_dim]   # [V, head_dim]
            self.rotated[h] = head_slice @ ors[h]               # [V, head_dim]

    def head_embeddings(self, head_id: int) -> np.ndarray:
        """Return rotated [V, head_dim] embeddings for a specific head."""
        if head_id not in self.rotated:
            s = head_id * self._head_dim
            return self.base[:, s : s + self._head_dim]
        return self.rotated[head_id]

    def all_heads_concatenated(self) -> np.ndarray:
        """
        Return [V, embed_dim] by concatenating all per-head rotated views.

        Each head's slice is individually rotated; the result has the same
        shape as the base embeddings but with decorrelated per-head features.
        """
        parts = [self.head_embeddings(h) for h in range(self.cfg.num_heads)]
        return np.concatenate(parts, axis=-1)
