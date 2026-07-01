"""Living-loop attention evolution — self-optimising kernel genome."""
from oss.living_loop.genome import KernelGenome
from oss.living_loop.experiments import run_attention_experiment, _build_ors_variant
from oss.living_loop.fitness import attention_fitness
from oss.living_loop.living_loop import LivingLoop

__all__ = [
    "KernelGenome",
    "run_attention_experiment",
    "_build_ors_variant",
    "attention_fitness",
    "LivingLoop",
]
