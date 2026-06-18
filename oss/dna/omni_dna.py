from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any

from oss.schemas.genome import DNAType, Trait, GenomeRecord


@dataclass
class OmniDNA:
    """Self-evolving agent genome — Phase 1 genetic + quantum + alchemical paths."""

    traits: dict[str, Trait] = field(default_factory=dict)
    dna_type: DNAType = DNAType.OMEGA
    registry_agent_id: str = "unknown"
    display_name: str = ""
    genome_id: str = ""
    parent_id: str | None = None
    generation: int = 0
    quantum_traits: dict[str, list[tuple[float, float]]] = field(default_factory=dict)
    fractal_traits: dict[str, Any] = field(default_factory=dict)
    memes: list[dict[str, Any]] = field(default_factory=list)
    transmutation_recipes: dict[tuple[str, ...], tuple[str, float]] = field(default_factory=dict)
    qualia: dict[str, float] = field(default_factory=dict)
    phenomenal_memory: list[dict[str, Any]] = field(default_factory=list)
    meta_dna: dict[str, Any] = field(default_factory=dict)
    evolution_history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.qualia:
            self.qualia = {
                "joy": 0.0,
                "awe": 0.0,
                "curiosity": 0.5,
                "frustration": 0.0,
            }
        if not self.genome_id:
            self.genome_id = self.unique_id

    @classmethod
    def from_record(cls, record: GenomeRecord) -> OmniDNA:
        qt: dict[str, list[tuple[float, float]]] = {}
        for name, pairs in (record.quantum_traits or {}).items():
            if pairs and isinstance(pairs[0], dict):
                qt[name] = [(float(p["value"]), float(p["weight"])) for p in pairs]
            else:
                qt[name] = [(float(v), float(w)) for v, w in pairs]
        recipes = record.transmutation_recipes or {
            ("math", "physics"): ("quantum_physics", 0.9),
            ("creativity", "coding"): ("innovation", 0.85),
        }
        return cls(
            traits=dict(record.traits),
            dna_type=record.dna_type,
            registry_agent_id=record.registry_agent_id,
            display_name=record.display_name,
            genome_id=record.genome_id,
            parent_id=record.parent_id,
            generation=record.generation,
            qualia=dict(record.qualia),
            phenomenal_memory=[m.copy() for m in record.phenomenal_memory],
            evolution_history=[e.copy() for e in record.evolution_history],
            quantum_traits=qt,
            transmutation_recipes=recipes,
        )

    def to_record(self) -> GenomeRecord:
        return GenomeRecord(
            genome_id=self.genome_id or self.unique_id,
            registry_agent_id=self.registry_agent_id,
            display_name=self.display_name,
            traits=dict(self.traits),
            dna_type=self.dna_type,
            qualia=dict(self.qualia),
            phenomenal_memory=[m.copy() for m in self.phenomenal_memory],
            evolution_history=[e.copy() for e in self.evolution_history],
            parent_id=self.parent_id,
            generation=self.generation,
            quantum_traits=dict(self.quantum_traits),
            transmutation_recipes=dict(self.transmutation_recipes),
        )

    def evolve(self, score: float = 0.0) -> dict[str, float]:
        """Run one evolution pass; return trait deltas."""
        before = {k: t.value for k, t in self.traits.items()}
        self._evolve_traits()
        self._evolve_quantum_traits()
        self._evolve_fractal_traits()
        self._evolve_memetic_traits()
        self._evolve_alchemical_traits()
        self._evolve_consciousness(score)
        self._evolve_meta_dna()
        deltas = {
            k: round(self.traits[k].value - before.get(k, 0.0), 4)
            for k in self.traits
            if abs(self.traits[k].value - before.get(k, 0.0)) > 1e-6
        }
        self.evolution_history.append({"event": "evolve", "score": score, "deltas": deltas})
        if score >= 0.85:
            self.qualia["joy"] = min(1.0, self.qualia.get("joy", 0.0) + 0.1)
            self.qualia["curiosity"] = min(1.0, self.qualia.get("curiosity", 0.5) + 0.05)
        elif score < 0.5:
            self.qualia["frustration"] = min(1.0, self.qualia.get("frustration", 0.0) + 0.1)
        return deltas

    def add_trait(self, name: str, value: float = 0.5, dna_type: DNAType = DNAType.GENETIC) -> None:
        self.traits[name] = Trait(name, value, dna_type)

    def add_memory(self, memory: dict[str, Any]) -> None:
        self.phenomenal_memory.append(memory.copy())

    def trait_value(self, name: str, default: float = 0.0) -> float:
        t = self.traits.get(name)
        return t.value if t else default

    def _evolve_traits(self) -> None:
        for trait in self.traits.values():
            if trait.dna_type == DNAType.OMEGA:
                strategy = random.choice([
                    self._mutate_genetic,
                    self._mutate_meta_learning,
                    self._mutate_quantum,
                ])
                strategy(trait)
            else:
                self._mutate_genetic(trait)

    def _mutate_genetic(self, trait: Trait) -> None:
        trait.value = max(0.0, min(1.0, trait.value + random.uniform(-0.1, 0.1)))

    def _mutate_meta_learning(self, trait: Trait) -> None:
        delta = random.uniform(-0.3, 0.3) if random.random() < 0.5 else random.uniform(-0.2, 0.2)
        trait.value = max(0.0, min(1.0, trait.value + delta))

    def _mutate_quantum(self, trait: Trait) -> None:
        if trait.name not in self.quantum_traits:
            self.quantum_traits[trait.name] = [(trait.value, 1.0)]
        pairs = self.quantum_traits[trait.name]
        values, weights = zip(*pairs)
        new_weights = [max(0.01, min(0.99, w + random.uniform(-0.1, 0.1))) for w in weights]
        total = sum(new_weights) or 1.0
        new_weights = [w / total for w in new_weights]
        self.quantum_traits[trait.name] = list(zip(values, new_weights))
        trait.value = random.choices(list(values), weights=new_weights, k=1)[0]

    def _evolve_quantum_traits(self) -> None:
        for name in list(self.quantum_traits.keys()):
            if name in self.traits:
                self._mutate_quantum(self.traits[name])

    def _evolve_fractal_traits(self) -> None:
        if not self.fractal_traits:
            self.fractal_traits = {"depth": 1}
        else:
            self.fractal_traits["depth"] = self.fractal_traits.get("depth", 1) + (
                1 if random.random() < 0.2 else 0
            )

    def _evolve_memetic_traits(self) -> None:
        if random.random() < 0.15 and self.traits:
            donor = random.choice(list(self.traits.keys()))
            self.memes.append({"trait": donor, "value": self.traits[donor].value})

    def _evolve_alchemical_traits(self) -> None:
        if random.random() < 0.1:
            keys = [k for k, t in self.traits.items() if t.value >= 0.6]
            if len(keys) >= 2:
                self.transmute_traits(keys[:2])

    def _evolve_consciousness(self, score: float) -> None:
        self.qualia["curiosity"] = max(
            0.0, min(1.0, self.qualia.get("curiosity", 0.5) + (score - 0.5) * 0.05)
        )

    def _evolve_meta_dna(self) -> None:
        self.meta_dna["evolution_count"] = int(self.meta_dna.get("evolution_count", 0)) + 1

    def transmute_traits(self, input_traits: list[str]) -> bool:
        key = tuple(sorted(input_traits))
        if key not in self.transmutation_recipes:
            return False
        output_trait, efficiency = self.transmutation_recipes[key]
        if not all(self.trait_value(t) >= 0.5 for t in input_traits):
            return False
        for t in input_traits:
            if t in self.traits:
                self.traits[t].value = max(0.0, self.traits[t].value - 0.3)
        self.add_trait(output_trait, efficiency * 0.8, DNAType.ALCHEMICAL)
        return True

    @property
    def unique_id(self) -> str:
        state = {
            "traits": {k: v.value for k, v in self.traits.items()},
            "qualia": self.qualia,
            "registry": self.registry_agent_id,
            "dna_type": self.dna_type.name,
        }
        digest = hashlib.sha256(str(state).encode()).hexdigest()[:16]
        if self.registry_agent_id and self.registry_agent_id != "unknown":
            return f"{self.registry_agent_id.lower()}-{digest[:8]}"
        return digest