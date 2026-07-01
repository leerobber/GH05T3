"""LivingLoop — per-genome attention evolution tracker with SentinelPrime governance."""
from __future__ import annotations

from typing import Any, Dict, List

from oss.living_loop.experiments import run_attention_experiment
from oss.living_loop.fitness import attention_fitness
from oss.living_loop.genome import KernelGenome
from oss.governance.sentinel_prime import SentinelPrime


class LivingLoop:
    """
    Tracks a population of KernelGenomes and runs iterative attention evolution.

    Each evolve_attention() tick:
      1. Runs a forward-pass experiment per registered genome
      2. Scores fitness from telemetry
      3. Sends scores to SentinelPrime for governance decisions
      4. Records everything in history
    """

    def __init__(self, substrate: Any) -> None:
        self.substrate = substrate
        self.genomes: Dict[str, KernelGenome] = {}
        self.history: Dict[str, List[Dict[str, Any]]] = {}
        self.sentinel = SentinelPrime()

    def register_genome(self, genome: KernelGenome) -> None:
        self.genomes[genome.genome_id] = genome
        self.history.setdefault(genome.genome_id, [])

    def record(self, genome_id: str, telemetry: Dict[str, Any], fitness: float) -> None:
        self.history.setdefault(genome_id, []).append(
            {"telemetry": telemetry, "fitness": fitness}
        )

    def evolve_attention(self) -> None:
        """Run one evolution tick for all registered genomes."""
        for genome_id, genome in self.genomes.items():
            telemetry = run_attention_experiment(genome, self.substrate)
            fitness = attention_fitness(telemetry)
            genome.fitness = fitness
            self.record(genome_id, telemetry, fitness)

            # Populate extra Sentinel axes with safe defaults if not in telemetry
            telemetry.setdefault("fitness_delta", fitness)
            telemetry.setdefault("trait_alignment", 0.5)
            telemetry.setdefault("genetic_coherence", 0.5)
            telemetry.setdefault("backend_parity", 0.5)
            telemetry.setdefault("trajectory", 0.5)

            scores = self.sentinel.score_genome(genome_id, telemetry)
            self.sentinel.record(genome_id, scores)
            telemetry["deployment_status"] = self.sentinel.decide(genome_id)
