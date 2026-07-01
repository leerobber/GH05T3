"""
DeployManager — uses SentinelPrime decisions to manage genome deployment slots.

Reads from a LivingLoop and SentinelPrime instance to classify each genome
as "active", "canary", or "retired", and surfaces the highest-fitness
active genome for production use.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from oss.governance.sentinel_prime import SentinelPrime


@dataclass
class DeploymentRecord:
    genome_id: str
    fitness: float
    status: str   # "active" | "canary" | "retired"


class DeployManager:
    """
    Syncs deployment records from LivingLoop + SentinelPrime.

    Usage:
        dm = DeployManager(sentinel=loop.sentinel)
        dm.sync_from_living_loop(loop)
        best = dm.select_active_genome()
    """

    def __init__(self, sentinel: SentinelPrime) -> None:
        self.sentinel = sentinel
        self.records: Dict[str, DeploymentRecord] = {}

    def sync_from_living_loop(self, loop: "Any") -> None:  # type: ignore[name-defined]
        """Pull latest genome fitness + Sentinel decisions into deployment records."""
        for genome_id, genome in loop.genomes.items():
            status = self.sentinel.decide(genome_id)
            self.records[genome_id] = DeploymentRecord(
                genome_id=genome_id,
                fitness=genome.fitness,
                status=status,
            )

    def select_active_genome(self) -> str | None:
        """Return the genome_id of the highest-fitness "active" genome, or None."""
        active = [r for r in self.records.values() if r.status == "active"]
        if not active:
            return None
        return max(active, key=lambda r: r.fitness).genome_id

    def select_canary_genome(self) -> str | None:
        """Return the highest-fitness "canary" genome, or None."""
        canaries = [r for r in self.records.values() if r.status == "canary"]
        if not canaries:
            return None
        return max(canaries, key=lambda r: r.fitness).genome_id

    def summary(self) -> Dict[str, List[str]]:
        """Return genome_ids bucketed by status."""
        out: Dict[str, List[str]] = {"active": [], "canary": [], "retired": []}
        for r in self.records.values():
            out.setdefault(r.status, []).append(r.genome_id)
        return out
