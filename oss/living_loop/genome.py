"""
KernelGenome — evolvable attention hyperparameter genome for LivingLoop.

Each KernelGenome encodes one set of MA-INBL attention hyperparameters.
LivingLoop experiments mutate, crossover, and select genomes to find
configurations that maximise telemetry-based fitness.
"""
from __future__ import annotations

import random
from dataclasses import dataclass


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass
class KernelGenome:
    """Evolvable genome for MA-INBL attention kernel hyperparameters."""

    genome_id: str
    fitness: float = 0.0
    block_size_l: int = 64
    block_size_dh: int = 64
    ors_variant: str = "qr"          # "qr", "identity", "random", "block_qr"
    int4_levels: int = 16            # 8, 16, 32
    training_binary_ratio: float = 1.0
    temperature: float = 1.0
    max_growth: float = 0.5
    use_torch: bool = False
    quant_mode: str = "ternary"    # "ternary" | "binary" — weight quantization mode

    def mutate(self) -> None:
        """Mutate this genome in place."""
        self.block_size_l = random.choice([32, 64, 128])
        self.block_size_dh = random.choice([32, 64, 128])
        self.ors_variant = random.choice(["qr", "identity", "random", "block_qr"])
        self.int4_levels = random.choice([8, 16, 32])
        self.training_binary_ratio = _clamp(
            self.training_binary_ratio + random.uniform(-0.1, 0.1), 0.0, 1.0)
        self.temperature = _clamp(
            self.temperature + random.uniform(-0.2, 0.2), 0.1, 10.0)
        self.max_growth = _clamp(
            self.max_growth + random.uniform(-0.1, 0.1), 0.0, 2.0)
        self.use_torch = random.choice([True, False])
        self.quant_mode = random.choice(["ternary", "binary"])

    def crossover(self, other: "KernelGenome") -> "KernelGenome":
        """Uniform crossover — produce a child genome combining genes from both parents."""
        child = KernelGenome(genome_id=f"{self.genome_id}+{other.genome_id}")
        child.block_size_l = random.choice([self.block_size_l, other.block_size_l])
        child.block_size_dh = random.choice([self.block_size_dh, other.block_size_dh])
        child.ors_variant = random.choice([self.ors_variant, other.ors_variant])
        child.int4_levels = random.choice([self.int4_levels, other.int4_levels])
        child.training_binary_ratio = (self.training_binary_ratio + other.training_binary_ratio) / 2.0
        child.temperature = (self.temperature + other.temperature) / 2.0
        child.max_growth = (self.max_growth + other.max_growth) / 2.0
        child.use_torch = random.choice([self.use_torch, other.use_torch])
        child.quant_mode = random.choice([self.quant_mode, other.quant_mode])
        return child
