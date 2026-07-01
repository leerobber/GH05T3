"""
LivingLoop attention experiments — run MA-INBL on genome trait vectors.

run_attention_experiment() is the core entry point: it pulls a genome's
trait vector from the substrate, builds an MA_INBLAttention module tuned
to the genome's hyperparameters, runs a forward pass, and returns the
telemetry dict augmented with canonical keys and output_norm.
"""
from __future__ import annotations

from typing import Any, Dict

import numpy as np

from oss.attention.attention import MA_INBLAttention
from oss.living_loop.genome import KernelGenome


def _build_ors_variant(
    variant: str,
    embed_dim: int,
    num_heads: int,
    head_dim: int,
) -> np.ndarray:
    """
    Build a [num_heads, head_dim, head_dim] per-head orthogonal rotation matrix.

    MA_INBLAttention accepts ors_matrix of shape (n_heads, head_dim, head_dim).
    """
    def _single_qr(seed: int) -> np.ndarray:
        rng = np.random.default_rng(seed)
        m = rng.standard_normal((head_dim, head_dim)).astype(np.float32)
        q, _ = np.linalg.qr(m)
        return q

    def _block_qr(seed: int) -> np.ndarray:
        rng = np.random.default_rng(seed)
        half = head_dim // 2
        tail = head_dim - half
        q1, _ = np.linalg.qr(rng.standard_normal((half, half)).astype(np.float32))
        q2, _ = np.linalg.qr(rng.standard_normal((tail, tail)).astype(np.float32))
        out = np.zeros((head_dim, head_dim), dtype=np.float32)
        out[:half, :half] = q1
        out[half:, half:] = q2
        return out

    per_head: list[np.ndarray] = []
    for h in range(num_heads):
        if variant == "identity":
            mat = np.eye(head_dim, dtype=np.float32)
        elif variant == "random":
            mat = _single_qr(42 + h)
        elif variant == "block_qr":
            mat = _block_qr(42 + h)
        else:  # "qr" (default)
            mat = _single_qr(h)
        per_head.append(mat)

    return np.stack(per_head, axis=0)  # [num_heads, head_dim, head_dim]


def run_attention_experiment(genome: KernelGenome, substrate: Any) -> Dict[str, Any]:
    """
    Run MA-INBL attention on a genome's trait vector and return telemetry.

    Pulls the segment from substrate, builds MA_INBLAttention from genome
    hyperparameters, runs a [1, 1, 32] forward pass, and returns the
    telemetry dict with canonical key aliases and output_norm added.
    """
    seg = substrate.segment(genome.genome_id)
    x = seg.trait_vector().astype(np.float32)   # [32]
    x = x.reshape(1, 1, -1)                     # [B=1, L=1, D=32]

    ors = _build_ors_variant(genome.ors_variant, embed_dim=32, num_heads=4, head_dim=8)
    attn = MA_INBLAttention(
        embed_dim=32,
        num_heads=4,
        training_binary_ratio=genome.training_binary_ratio,
        temperature=genome.temperature,
        max_growth=genome.max_growth,
        ors_matrix=ors,
    )
    y, telemetry = attn.forward(x)

    # Canonical key aliases so callers don't need to know kernel-internal names
    telemetry["mean_mag_x"] = float(telemetry.get("x_mag_mean", 0.0))
    telemetry["mean_candidate_mag"] = float(telemetry.get("cand_mag_mean", 0.0))
    telemetry["mean_mgc_scale"] = float(telemetry.get("mgc_scale_mean", 1.0))
    telemetry["output_norm"] = float(np.linalg.norm(y))
    telemetry["genome_id"] = genome.genome_id
    return telemetry
