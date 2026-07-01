"""
SubstrateModel — stacked SubstrateBlocks with MA_INBLAttention.

Configured from AttentionConfig (genome-derived) or raw hyperparameters.
Runs entirely on the numpy backend (no GPU/torch required).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from oss.substrate.attention_config import AttentionConfig
from oss.substrate.blocks import BlockConfig, SubstrateBlock


@dataclass
class SubstrateConfig:
    """
    Full configuration for a SubstrateModel.

    Attention hyperparameters mirror AttentionConfig so that a model can be
    derived directly from a genome's trait profile via from_attention_config().
    """

    embed_dim: int = 32
    num_heads: int = 4
    num_layers: int = 2
    ffn_dim: int = 128
    attn_temperature: float = 1.0
    attn_max_growth: float = 0.5
    attn_binary_ratio: float = 0.0
    attn_training_binary_ratio: float = 1.0
    attn_seed: int = 0
    attn_backend: str = "auto"     # "auto" | "numpy" | "triton"
    ors_matrix: np.ndarray | None = field(default=None, repr=False)

    # ── factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_attention_config(
        cls,
        attn_cfg: AttentionConfig,
        *,
        num_layers: int = 2,
        ffn_multiplier: int = 4,
        ors_matrix: np.ndarray | None = None,
    ) -> "SubstrateConfig":
        """Derive a SubstrateConfig from a genome's AttentionConfig."""
        return cls(
            embed_dim=attn_cfg.embed_dim,
            num_heads=attn_cfg.num_heads,
            num_layers=num_layers,
            ffn_dim=attn_cfg.embed_dim * ffn_multiplier,
            attn_temperature=attn_cfg.temperature,
            attn_max_growth=attn_cfg.max_growth,
            attn_binary_ratio=attn_cfg.binary_ratio,
            attn_training_binary_ratio=attn_cfg.training_binary_ratio,
            attn_seed=attn_cfg.seed,
            attn_backend=attn_cfg.backend,
            ors_matrix=ors_matrix,
        )

    def to_block_config(self) -> BlockConfig:
        return BlockConfig(
            embed_dim=self.embed_dim,
            num_heads=self.num_heads,
            ffn_dim=self.ffn_dim,
            attn_temperature=self.attn_temperature,
            attn_max_growth=self.attn_max_growth,
            attn_binary_ratio=self.attn_binary_ratio,
            attn_training_binary_ratio=self.attn_training_binary_ratio,
            attn_seed=self.attn_seed,
            attn_backend=self.attn_backend,
            ors_matrix=self.ors_matrix,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "embed_dim": self.embed_dim,
            "num_heads": self.num_heads,
            "num_layers": self.num_layers,
            "ffn_dim": self.ffn_dim,
            "attn_temperature": self.attn_temperature,
            "attn_max_growth": self.attn_max_growth,
            "attn_binary_ratio": self.attn_binary_ratio,
            "attn_training_binary_ratio": self.attn_training_binary_ratio,
            "attn_seed": self.attn_seed,
            "has_ors_matrix": self.ors_matrix is not None,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SubstrateConfig":
        return cls(
            embed_dim=int(d.get("embed_dim", 32)),
            num_heads=int(d.get("num_heads", 4)),
            num_layers=int(d.get("num_layers", 2)),
            ffn_dim=int(d.get("ffn_dim", 128)),
            attn_temperature=float(d.get("attn_temperature", 1.0)),
            attn_max_growth=float(d.get("attn_max_growth", 0.5)),
            attn_binary_ratio=float(d.get("attn_binary_ratio", 0.0)),
            attn_training_binary_ratio=float(d.get("attn_training_binary_ratio", 1.0)),
            attn_seed=int(d.get("attn_seed", 0)),
        )


class SubstrateModel:
    """
    Multi-layer transformer model using MA_INBLAttention in every block.

    Forward pass: x [seq, D] → y [seq, D] + list of per-block telemetry dicts.

    This is the core substrate forward path — the genome's trait profile shapes
    every attention block's temperature, growth clamping, and binary ratio.
    """

    def __init__(self, cfg: SubstrateConfig) -> None:
        self.cfg = cfg
        block_cfg = cfg.to_block_config()
        self.blocks: list[SubstrateBlock] = [
            SubstrateBlock(block_cfg) for _ in range(cfg.num_layers)
        ]
        # Input projection: if input dim ≠ embed_dim, project up/down
        rng = np.random.default_rng(cfg.attn_seed)
        self._in_proj: np.ndarray | None = None   # identity when dims match

    def forward(
        self,
        x: np.ndarray,
    ) -> tuple[np.ndarray, list[dict[str, Any]]]:
        """
        Run the full substrate forward pass.

        x       : [seq, embed_dim] or [batch, seq, embed_dim] float32
        Returns : (output, list_of_block_telemetry)
        """
        tel_list: list[dict[str, Any]] = []
        h = x.astype(np.float32)
        for block in self.blocks:
            h, tel = block.forward(h)
            tel_list.append(tel)
        return h, tel_list

    def attention_modules(self):
        """Yield (layer_idx, MA_INBLAttention) for each block."""
        for i, block in enumerate(self.blocks):
            yield i, block.attn

    @property
    def embed_dim(self) -> int:
        return self.cfg.embed_dim

    @property
    def num_layers(self) -> int:
        return self.cfg.num_layers
