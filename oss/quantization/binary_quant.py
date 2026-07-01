"""
BitNet-style binary / ternary quantization for MA-INBL projections.

Weight quantization maps float32 matrices to ternary {-1, 0, +1} or
binary {-1, +1}, plus a per-matrix absmean scale factor.  Activation
quantization uses per-token absmax scaling to INT8 range.

The matmul() method performs the addition-only matrix multiply by
splitting the ternary weight into positive and negative masks so all
arithmetic reduces to additions instead of multiplications.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

import numpy as np


@dataclass
class BinaryQuantConfig:
    mode: str = "ternary"      # "ternary" ({-1,0,+1}) | "binary" ({-1,+1})
    threshold: float = 0.5     # ternary dead-zone: |w_norm| ≤ threshold → 0
    act_bits: int = 8          # activation quantization bits (absmax INT8)


class BinaryQuantizer:
    """
    BitNet-style weight + activation quantizer.

    Usage (inference projection):
        q = BinaryQuantizer()
        W_q, W_s = q.quantize_weights(W)          # once at init
        x_q, x_s = q.quantize_activations(x)      # per forward pass
        y = q.matmul(x_q, W_q, W_s) * x_s        # addition-only + rescale
    """

    def __init__(self, cfg: BinaryQuantConfig | None = None) -> None:
        self.cfg = cfg or BinaryQuantConfig()

    # ------------------------------------------------------------------
    def quantize_weights(self, W: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Quantize a weight matrix.

        W : [in, out] float32
        Returns
        -------
        W_q : same shape, dtype float32, values in {-1, 0, +1} or {-1, +1}
        scale : float — absmean scale to dequantize with
        """
        W = W.astype(np.float32)
        scale = float(np.mean(np.abs(W)))
        if scale == 0.0:
            scale = 1.0
        W_norm = W / scale

        if self.cfg.mode == "ternary":
            t = self.cfg.threshold
            W_q = np.zeros_like(W_norm)
            W_q[W_norm > t] = 1.0
            W_q[W_norm < -t] = -1.0
        else:  # binary
            W_q = np.sign(W_norm).astype(np.float32)
            W_q[W_q == 0.0] = 1.0  # tie-break zeros to +1

        return W_q.astype(np.float32), scale

    # ------------------------------------------------------------------
    def quantize_activations(
        self, x: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Per-token absmax activation quantization.

        x : [..., D] float32
        Returns
        -------
        x_q    : same shape float32, values scaled to [-127, 127]
        scales : [..., 1] float32 — per-token absmax
        """
        x = x.astype(np.float32)
        max_int = float(2 ** (self.cfg.act_bits - 1) - 1)  # 127 for 8-bit
        scales = np.max(np.abs(x), axis=-1, keepdims=True).astype(np.float32)
        scales = np.where(scales == 0.0, np.ones_like(scales), scales)
        x_q = np.clip(np.round(x / scales * max_int), -max_int, max_int).astype(
            np.float32
        )
        return x_q, scales

    # ------------------------------------------------------------------
    def dequantize(
        self, q: np.ndarray, scale: float | np.ndarray
    ) -> np.ndarray:
        """Multiply quantized values by scale to recover approximate float."""
        return q.astype(np.float32) * scale

    # ------------------------------------------------------------------
    def matmul(
        self, x: np.ndarray, W_q: np.ndarray, W_scale: float
    ) -> np.ndarray:
        """
        Addition-only matrix multiply for ternary/binary weights.

        Splits W_q into positive and negative masks and uses only additions:
            y = (x @ pos_mask) - (x @ neg_mask)

        x     : [..., in_features] float32
        W_q   : [in_features, out_features] float32, values in {-1, 0, +1}
        W_scale : absmean weight scale
        Returns : [..., out_features] float32
        """
        x = x.astype(np.float32)
        pos = (W_q == 1.0).astype(np.float32)   # [in, out]
        neg = (W_q == -1.0).astype(np.float32)  # [in, out]
        y = (x @ pos) - (x @ neg)               # addition only
        return y * W_scale
