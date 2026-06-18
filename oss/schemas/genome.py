from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class DNAType(Enum):
    GENETIC = auto()
    META_LEARNING = auto()
    SELF_REFERENTIAL = auto()
    HYPERGRAPH = auto()
    CONSCIOUSNESS = auto()
    QUANTUM = auto()
    FRACTAL = auto()
    MEMETIC = auto()
    ALCHEMICAL = auto()
    HOLOGRAPHIC = auto()
    OMEGA = auto()


@dataclass
class Trait:
    name: str
    value: float
    dna_type: DNAType = DNAType.GENETIC
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "dna_type": self.dna_type.name,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Trait:
        return cls(
            name=data["name"],
            value=float(data["value"]),
            dna_type=DNAType[data.get("dna_type", "GENETIC")],
            metadata=data.get("metadata") or {},
        )


@dataclass
class GenomeRecord:
    """Persisted genome linked to an agent_registry slug."""

    genome_id: str
    registry_agent_id: str
    display_name: str
    traits: dict[str, Trait] = field(default_factory=dict)
    dna_type: DNAType = DNAType.OMEGA
    qualia: dict[str, float] = field(default_factory=dict)
    phenomenal_memory: list[dict[str, Any]] = field(default_factory=list)
    evolution_history: list[dict[str, Any]] = field(default_factory=list)
    parent_id: str | None = None
    generation: int = 0
    quantum_traits: dict[str, list[tuple[float, float]]] = field(default_factory=dict)
    transmutation_recipes: dict[tuple[str, ...], tuple[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "genome_id": self.genome_id,
            "registry_agent_id": self.registry_agent_id,
            "display_name": self.display_name,
            "traits": {k: v.to_dict() for k, v in self.traits.items()},
            "dna_type": self.dna_type.name,
            "qualia": self.qualia,
            "phenomenal_memory": self.phenomenal_memory,
            "evolution_history": self.evolution_history,
            "parent_id": self.parent_id,
            "generation": self.generation,
            "quantum_traits": {
                k: [{"value": v, "weight": w} for v, w in pairs]
                for k, pairs in self.quantum_traits.items()
            },
        }


@dataclass
class SwarmTask:
    problem: str
    required_traits: list[str] = field(default_factory=list)
    max_agents: int = 5
    task_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "problem": self.problem,
            "required_traits": self.required_traits,
            "max_agents": self.max_agents,
            "task_id": self.task_id,
            "metadata": self.metadata,
        }


@dataclass
class SwarmResult:
    task_id: str
    problem: str
    agents: list[str]
    responses: list[dict[str, Any]]
    synthesis: str
    score: float
    kairos_cycle_id: int | None = None
    trait_deltas: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "problem": self.problem,
            "agents": self.agents,
            "responses": self.responses,
            "synthesis": self.synthesis,
            "score": self.score,
            "kairos_cycle_id": self.kairos_cycle_id,
            "trait_deltas": self.trait_deltas,
        }