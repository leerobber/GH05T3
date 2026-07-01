"""
MetaScheduler — runs evolution epochs under different objectives and adapts
strategy when improvement stalls.

Coordinates LivingLoop, SentinelPrime, and ObjectiveRouter to produce a
self-adjusting evolution loop without external orchestration services.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict

from oss.goals.objective_router import ObjectiveRouter
from oss.governance.sentinel_prime import SentinelPrime

if TYPE_CHECKING:
    from oss.living_loop.living_loop import LivingLoop


@dataclass
class ScheduleConfig:
    max_cycles_per_epoch: int = 5
    min_fitness_delta: float = 0.01


class MetaScheduler:
    """
    Runs evolution epochs under different objectives and adapts strategy
    when fitness improvement stalls.

    Each run_epoch() call:
      1. Sets the current objective on ObjectiveRouter
      2. Runs max_cycles_per_epoch LivingLoop ticks
      3. Reports best/mean fitness
      4. Switches to "exploration" if improvement < min_fitness_delta
    """

    def __init__(
        self,
        loop: LivingLoop,
        sentinel: SentinelPrime,
        objectives: ObjectiveRouter,
        config: ScheduleConfig | None = None,
    ) -> None:
        self.loop = loop
        self.sentinel = sentinel
        self.objectives = objectives
        self.config = config or ScheduleConfig()
        self._last_best_fitness: float | None = None

    def run_epoch(self, objective: str) -> Dict[str, Any]:
        """
        Run one full evolution epoch under the given objective.

        Returns a summary dict with objective, best_fitness, mean_fitness,
        stalled flag, and per-genome Sentinel decisions.
        """
        self.objectives.set_objective(objective)

        for _ in range(self.config.max_cycles_per_epoch):
            self.loop.evolve_attention()

        fitness_values = [g.fitness for g in self.loop.genomes.values()]
        best_fitness = max(fitness_values) if fitness_values else 0.0
        mean_fitness = sum(fitness_values) / max(len(fitness_values), 1)

        stalled = False
        if self._last_best_fitness is not None:
            delta = best_fitness - self._last_best_fitness
            if delta < self.config.min_fitness_delta:
                self.objectives.set_objective("exploration")
                stalled = True

        self._last_best_fitness = best_fitness

        return {
            "objective": objective,
            "best_fitness": round(best_fitness, 4),
            "mean_fitness": round(mean_fitness, 4),
            "stalled": stalled,
            "sentinel_decisions": self.sentinel.status_summary(),
        }
