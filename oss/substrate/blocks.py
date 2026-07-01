"""
SubstrateBlock — single transformer block using MA_INBLAttention.

Each block is a standard pre-norm attention + feedforward unit.
The attention module is built via AttentionConfig so genome-derived backend
selection (numpy vs Triton) propagates automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class BlockConfig:
    """Hyperparameters for one SubstrateBlock."""

    embed_dim: int = 32
    num_heads: int = 4
    ffn_dim: int = 128             # feed-forward hidden size (4 × embed_dim default)
    dropout: float = 0.0           # not applied in numpy reference
    attn_temperature: float = 1.0
    attn_max_growth: float = 0.5
    attn_binary_ratio: float = 0.0
    attn_training_binary_ratio: float = 1.0
    attn_seed: int = 0
    attn_backend: str = "auto"     # "auto" | "numpy" | "triton"
    ors_matrix: np.ndarray | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.ffn_dim == 128 and self.embed_dim != 32:
            self.ffn_dim = 4 * self.embed_dim


class SubstrateBlock:
    """
    Pre-norm attention + feedforward block using MA_INBLAttention.

    Input/output shape: [seq_len, embed_dim] (2-D) or [batch, seq_len, embed_dim] (3-D).
    The feedforward sub-layer is a simple numpy two-layer MLP with GELU activation.
    """

    def __init__(self, cfg: BlockConfig) -> None:
        self._cfg = cfg
        self._embed_dim = cfg.embed_dim
        self._ffn_dim = cfg.ffn_dim

        # Build via AttentionConfig so genome-driven backend selection applies
        from oss.substrate.attention_config import AttentionConfig
        _attn_cfg = AttentionConfig(
            embed_dim=cfg.embed_dim,
            num_heads=cfg.num_heads,
            binary_ratio=cfg.attn_binary_ratio,
            training_binary_ratio=cfg.attn_training_binary_ratio,
            temperature=cfg.attn_temperature,
            max_growth=cfg.attn_max_growth,
            seed=cfg.attn_seed,
            backend=getattr(cfg, "attn_backend", "auto"),
        )
        self.attn = _attn_cfg.build_module()

        # Layer-norm scale/bias (learned — initialised to identity)
        self._ln1_w = np.ones(cfg.embed_dim, dtype=np.float32)
        self._ln1_b = np.zeros(cfg.embed_dim, dtype=np.float32)
        self._ln2_w = np.ones(cfg.embed_dim, dtype=np.float32)
        self._ln2_b = np.zeros(cfg.embed_dim, dtype=np.float32)

        # Feed-forward weights (He init)
        rng = np.random.default_rng(cfg.attn_seed)
        self._ffn_w1 = rng.standard_normal((cfg.embed_dim, cfg.ffn_dim)).astype(np.float32) * np.sqrt(2.0 / cfg.embed_dim)
        self._ffn_b1 = np.zeros(cfg.ffn_dim, dtype=np.float32)
        self._ffn_w2 = rng.standard_normal((cfg.ffn_dim, cfg.embed_dim)).astype(np.float32) * np.sqrt(2.0 / cfg.ffn_dim)
        self._ffn_b2 = np.zeros(cfg.embed_dim, dtype=np.float32)

    # ── public ────────────────────────────────────────────────────────────────

    def forward(self, x: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
        """
        Forward pass.

        x        : [seq, D] or [batch, seq, D] float32
        Returns  : (output same shape as x, telemetry dict)
        """
        squeeze = x.ndim == 2
        if squeeze:
            x = x[None, ...]          # add batch dim → [1, seq, D]

        batch, seq, d = x.shape
        tel_all: list[dict] = []
        out = np.empty_like(x)

        for b in range(batch):
            xi = x[b]                 # [seq, D]
            # Pre-norm 1
            h = self._layer_norm(xi, self._ln1_w, self._ln1_b)
            attn_out, tel = self.attn.forward(h)
            tel_all.append(tel)
            xi = xi + attn_out        # residual

            # Pre-norm 2 → FFN
            h2 = self._layer_norm(xi, self._ln2_w, self._ln2_b)
            ffn_out = self._ffn(h2)
            out[b] = xi + ffn_out     # residual

        if squeeze:
            out = out[0]              # strip batch dim

        merged_tel = self._merge_tel(tel_all)
        return out, merged_tel

    # ── private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _layer_norm(
        x: np.ndarray,
        w: np.ndarray,
        b: np.ndarray,
        eps: float = 1e-5,
    ) -> np.ndarray:
        mu = x.mean(axis=-1, keepdims=True)
        var = x.var(axis=-1, keepdims=True)
        return w * (x - mu) / np.sqrt(var + eps) + b

    def _ffn(self, x: np.ndarray) -> np.ndarray:
        """Two-layer MLP: Linear → GELU → Linear."""
        h = x @ self._ffn_w1 + self._ffn_b1
        h = self._gelu(h)
        return h @ self._ffn_w2 + self._ffn_b2

    @staticmethod
    def _gelu(x: np.ndarray) -> np.ndarray:
        return 0.5 * x * (1.0 + np.tanh(np.sqrt(2.0 / np.pi) * (x + 0.044715 * x ** 3)))

    @staticmethod
    def _merge_tel(tels: list[dict]) -> dict:
        if not tels:
            return {}
        keys = tels[0].keys()
        merged: dict[str, Any] = {}
        for k in keys:
            vals = [t[k] for t in tels if isinstance(t.get(k), (int, float))]
            merged[k] = float(np.mean(vals)) if vals else tels[0].get(k)
        return merged
