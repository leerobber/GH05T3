"""Fitness function for LivingLoop MA-INBL attention experiments."""
from __future__ import annotations

from typing import Dict


def attention_fitness(telemetry: Dict[str, float]) -> float:
    """
    Compute scalar fitness from MA-INBL attention telemetry.

    Higher MGC scale (growth well-controlled), lower entropy, and larger
    output norm all contribute positively.
    """
    mgc_scale = float(telemetry.get("mean_mgc_scale", 1.0))
    entropy = float(telemetry.get("mean_attn_entropy", 0.0))
    output_norm = float(telemetry.get("output_norm", 0.0))
    return mgc_scale - 0.1 * entropy + 0.01 * output_norm
