"""
Binary semantic compression.

Encodes a small semantic feature vector into a compact B-bit binary code
and decodes it back.  The encoder/decoder weights can be genome-driven:
richer genomes evolve better projections.

Usage:
    sc = SemanticCodecs()
    code = sc.encode(features)     # [code_bits] float32 ∈ {0, 1}
    recon = sc.decode(code)        # [feature_dim] float32
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SemanticCodeConfig:
    feature_dim: int = 16   # F — input semantic feature dimension
    code_bits: int = 8      # B — output binary code length


class SemanticCodecs:
    """
    Stateless encode/decode.  Encoder weights are initialised with a
    near-orthogonal projection so bits stay balanced at init time.

    Weights can be replaced by a genome-evolved matrix to improve
    reconstruction quality over training cycles.
    """

    def __init__(self, cfg: SemanticCodeConfig | None = None, seed: int = 0) -> None:
        self.cfg = cfg or SemanticCodeConfig()
        rng = np.random.default_rng(seed)
        # Near-orthogonal init: QR of a random [F, B] matrix
        A = rng.standard_normal((self.cfg.feature_dim, self.cfg.code_bits)).astype(np.float32)
        if self.cfg.feature_dim >= self.cfg.code_bits:
            Q, _ = np.linalg.qr(A)
            self.encoder_W: np.ndarray = Q[:, : self.cfg.code_bits]
        else:
            self.encoder_W = A / (np.linalg.norm(A, axis=0, keepdims=True) + 1e-8)
        self.decoder_W: np.ndarray = self.encoder_W.T  # Approximate left-inverse

    def encode(self, features: np.ndarray) -> np.ndarray:
        """
        Project [F] semantic features to [B] binary code.

        Accepts shapes [..., F]; returns [..., B] float32 ∈ {0, 1}.
        """
        z = features.astype(np.float32) @ self.encoder_W
        return (z > 0.0).astype(np.float32)

    def decode(self, code: np.ndarray) -> np.ndarray:
        """
        Reconstruct approximate [F] features from [B] binary code.

        Accepts shapes [..., B]; returns [..., F] float32.
        """
        return code.astype(np.float32) @ self.decoder_W

    def reconstruction_error(self, features: np.ndarray) -> float:
        """Round-trip MSE — useful as a fitness signal."""
        code = self.encode(features)
        recon = self.decode(code)
        return float(np.mean((features.astype(np.float32) - recon) ** 2))

    def set_weights(self, encoder_W: np.ndarray) -> None:
        """Replace encoder weights (e.g. from genome evolution)."""
        self.encoder_W = encoder_W.astype(np.float32)
        self.decoder_W = self.encoder_W.T
