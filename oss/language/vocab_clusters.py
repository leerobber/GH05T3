"""
Binary-coded vocabulary clustering.

Groups token embeddings into K clusters via k-means, then assigns each cluster
a unique B-bit binary code.  MA-INBL attention heads can specialize over these
codes instead of raw float embeddings.

Telemetry: cluster balance (std of token counts per cluster).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import numpy as np

try:
    from sklearn.cluster import KMeans
except ImportError:
    class KMeans:  # type: ignore[no-redef]
        """Minimal fallback when sklearn is absent: random cluster assignment."""
        def __init__(self, n_clusters: int = 64, n_init: int = 1, random_state: int = 0) -> None:
            self.n_clusters = n_clusters
            self._rng = np.random.default_rng(random_state)
        def fit_predict(self, X: np.ndarray) -> np.ndarray:
            return self._rng.integers(0, self.n_clusters, len(X))


@dataclass
class VocabClusterConfig:
    n_clusters: int = 64   # K — number of semantic clusters
    code_bits: int = 8     # B — bits per binary cluster code


class VocabClusters:
    """
    Fits k-means clusters over token embeddings and assigns each token a
    B-bit binary code derived from its cluster ID.

    Usage:
        vc = VocabClusters(embeddings)
        vc.fit_clusters()
        code = vc.code_for_token(token_id)   # [code_bits] float32 ∈ {0, 1}
    """

    def __init__(
        self,
        embeddings: np.ndarray,
        cfg: VocabClusterConfig | None = None,
    ) -> None:
        self.cfg = cfg or VocabClusterConfig()
        self.embeddings = embeddings.astype(np.float32)
        self.cluster_ids: np.ndarray | None = None
        self.codes: Dict[int, np.ndarray] = {}
        self.telemetry: Dict[str, float] = {}

    def fit_clusters(self) -> None:
        """Run k-means and precompute binary codes for all token IDs."""
        V = len(self.embeddings)
        kmeans = KMeans(
            n_clusters=min(self.cfg.n_clusters, V),
            n_init=4,
            random_state=0,
        )
        self.cluster_ids = kmeans.fit_predict(self.embeddings)

        for token_id in range(V):
            cid = int(self.cluster_ids[token_id])
            self.codes[token_id] = self._cluster_id_to_code(cid)

        unique, counts = np.unique(self.cluster_ids, return_counts=True)
        self.telemetry = {
            "n_clusters_used": int(len(unique)),
            "balance_std": float(np.std(counts / V)),
            "mean_tokens_per_cluster": float(counts.mean()),
        }

    def _cluster_id_to_code(self, cid: int) -> np.ndarray:
        bits = np.zeros(self.cfg.code_bits, dtype=np.float32)
        for i in range(min(self.cfg.code_bits, 32)):
            if (cid >> i) & 1:
                bits[i] = 1.0
        return bits

    def code_for_token(self, token_id: int) -> np.ndarray:
        """Return the B-bit binary code for a given token ID."""
        return self.codes.get(token_id, np.zeros(self.cfg.code_bits, dtype=np.float32))

    def encode_sequence(self, token_ids: np.ndarray) -> np.ndarray:
        """
        Encode a sequence of token IDs to binary codes.

        token_ids : [L] or [B, L] int array
        Returns   : same shape + code_bits last dim, float32 ∈ {0, 1}
        """
        flat = token_ids.ravel()
        codes = np.stack([self.code_for_token(int(t)) for t in flat])
        return codes.reshape(*token_ids.shape, self.cfg.code_bits)
