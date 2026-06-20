"""
Speciation Layer — Species Divergence Experiments (Omni-Evolution Phase 10)

This completes the speciation layer.

Core ideas:
- Agents / populations diverge into distinct *species* when trait + meta-DNA distance exceeds threshold.
- Each species has its own specialized meta-DNA (evolution rules evolve per lineage).
- Reproductive / memetic isolation: high divergence species no longer share traits or crossover.
- Divergence pressure: different sub-tasks / niches drive branching (e.g. one species specializes in Volatility, another in Alignment tradeoffs).
- Phylogeny tracking: tree of speciation events.
- Experiments: run isolated populations, measure successful new species, fitness in their niche.

Integrates with:
- OmniDNA (species_id, meta_dna per species)
- GenomicSubstrate (multi-species genomes)
- Evolution (per-species adaptive rules + isolation)
- TheoryLab / curriculum (divergence tasks)
- SpeciesMemory (speciation events + divergence metrics)
- Omni-Net (species-aware broadcast)
- MVS

Run experiments:
  python -m backend.oss.speciation_phase --experiments 5 --cycles_per 20
"""

from __future__ import annotations
import json
import random
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Any, Optional

from backend.oss.omni_dna import OmniDNA, UNIVERSAL_TRAITS
from backend.oss.species_memory import get_species_memory


@dataclass
class Species:
    species_id: str
    parent_id: Optional[str]
    birth_cycle: int
    meta_dna: Dict[str, float] = field(default_factory=dict)  # evolution rules for this species
    niche: str = "general"  # e.g. "volatility", "alignment", "meta"
    trait_signature: Dict[str, float] = field(default_factory=dict)  # average traits at speciation


@dataclass
class SpeciationEvent:
    timestamp: float
    parent_species: str
    new_species: str
    divergence: float
    trigger: str
    niche: str


class SpeciationEngine:
    def __init__(self, divergence_threshold: float = 0.12):
        self.divergence_threshold = divergence_threshold
        self.species: Dict[str, Species] = {}
        self.events: List[SpeciationEvent] = []
        self._load_state()
        # Lazy to avoid circular import with mvs
        self._mvs = None
        self._memory = None

    @property
    def mvs(self):
        if self._mvs is None:
            from backend.oss.mvs import get_mvs
            self._mvs = get_mvs()
        return self._mvs

    @property
    def substrate(self):
        return self.mvs["substrate"]

    @property
    def memory(self):
        if self._memory is None:
            self._memory = get_species_memory()
        return self._memory

    def _load_state(self):
        p = Path("data/speciation_state.json")
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self.species = {k: Species(**v) for k, v in data.get("species", {}).items()}
                self.events = [SpeciationEvent(**e) for e in data.get("events", [])]
            except Exception:
                pass

    def _save_state(self):
        p = Path("data/speciation_state.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "species": {k: asdict(v) for k, v in self.species.items()},
            "events": [asdict(e) for e in self.events],
        }
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_or_create_species(self, species_id: str, parent: Optional[str] = None, niche: str = "general") -> Species:
        if species_id not in self.species:
            self.species[species_id] = Species(
                species_id=species_id,
                parent_id=parent,
                birth_cycle=len(self.events),
                niche=niche,
                meta_dna={k: 0.5 + random.uniform(-0.1, 0.1) for k in ["mutation_rate", "selection_pressure", "crossover_bias"]},
            )
        return self.species[species_id]

    def calculate_divergence(self, dna1: OmniDNA, dna2: OmniDNA) -> float:
        """Simple multi-trait + meta distance."""
        t1 = dna1.get_traits()
        t2 = dna2.get_traits()
        trait_dist = sum(abs(t1.get(k, 0.5) - t2.get(k, 0.5)) for k in UNIVERSAL_TRAITS) / len(UNIVERSAL_TRAITS)

        # Meta-DNA divergence if available
        meta_dist = 0.0
        if hasattr(dna1, 'get_meta_dna') and hasattr(dna2, 'get_meta_dna'):
            m1 = dna1.get_meta_dna()
            m2 = dna2.get_meta_dna()
            if m1 and m2:
                meta_dist = sum(abs(m1.get(k, 0.5) - m2.get(k, 0.5)) for k in m1) / max(1, len(m1))

        return (trait_dist * 0.7 + meta_dist * 0.3)

    def measure_group_divergence(self, genome_ids: List[str]) -> float:
        """Average pairwise divergence for a genome group (0.0 if insufficient data)."""
        genomes = [
            self.substrate.genomes[gid].dna
            for gid in genome_ids
            if gid in self.substrate.genomes
        ]
        if len(genomes) < 2:
            return 0.0
        divergences = []
        for i in range(len(genomes)):
            for j in range(i + 1, len(genomes)):
                divergences.append(self.calculate_divergence(genomes[i], genomes[j]))
        return sum(divergences) / len(divergences)

    def _resolve_parent_species(self, genome_ids: List[str]) -> str:
        parents = set()
        for gid in genome_ids:
            if gid not in self.substrate.genomes:
                continue
            dna = self.substrate.genomes[gid].dna
            parents.add(getattr(dna, "species_id", None) or "ROOT")
        if len(parents) == 1:
            return parents.pop()
        return "ROOT"

    def attempt_speciation(self, genome_ids: List[str], current_cycle: int, niche: str = "general") -> List[str]:
        """
        Check a group of genomes. If average pairwise divergence high, split off a new species.
        Returns list of newly created species_ids.
        """
        if len(genome_ids) < 3:
            return []

        new_species = []
        genomes = [(gid, self.substrate.genomes[gid].dna) for gid in genome_ids if gid in self.substrate.genomes]

        # Compute pairwise
        divergences = []
        for i in range(len(genomes)):
            for j in range(i+1, len(genomes)):
                d = self.calculate_divergence(genomes[i][1], genomes[j][1])
                divergences.append(d)

        if not divergences:
            return []

        avg_div = sum(divergences) / len(divergences)

        if avg_div > self.divergence_threshold:
            # Pick the most divergent individual(s) as founders of new species
            # For simplicity: split the group roughly in half by some trait (e.g. highest novelty vs others)
            sorted_g = sorted(genomes, key=lambda x: x[1].get_traits().get("novelty_seeking", 0.5))
            split_point = len(sorted_g) // 2
            new_group = [g[0] for g in sorted_g[split_point:]]

            if len(new_group) >= 2:
                new_id = f"SPECIES-{len(self.species) + 1:03d}-{int(time.time()) % 10000}"
                parent_id = self._resolve_parent_species(genome_ids)

                sp = self.get_or_create_species(new_id, parent=parent_id, niche=niche)
                trait_sums: Dict[str, float] = {}
                trait_counts = 0
                for gid in new_group:
                    rec = self.substrate.genomes[gid]
                    for k, v in rec.dna.get_traits().items():
                        trait_sums[k] = trait_sums.get(k, 0.0) + v
                    trait_counts += 1
                if trait_counts:
                    sp.trait_signature = {
                        k: round(v / trait_counts, 4) for k, v in trait_sums.items()
                    }
                # Specialize meta for the new species
                for k in sp.meta_dna:
                    sp.meta_dna[k] = max(0.1, min(0.9, sp.meta_dna[k] + random.uniform(-0.15, 0.15)))

                # Tag the new genomes
                for gid in new_group:
                    rec = self.substrate.genomes[gid]
                    rec.dna.species_id = new_id
                    if not hasattr(rec.dna, 'species_id'):
                        rec.dna.species_id = new_id

                event = SpeciationEvent(
                    timestamp=time.time(),
                    parent_species=parent_id,
                    new_species=new_id,
                    divergence=round(avg_div, 3),
                    trigger="high_pairwise_divergence",
                    niche=niche,
                )
                self.events.append(event)
                new_species.append(new_id)
                self._save_state()

                # Record in species memory
                try:
                    self.memory.record_phase(
                        model_version=f"speciation-{new_id}",
                        mean_fitness=avg_div,
                        std_fitness=0.0,
                        trait_means={},
                        trait_stds={"divergence": avg_div},
                        population_size=len(new_group),
                        notes=f"speciated from {parent_id} in {niche}",
                    )
                except Exception:
                    pass

        return new_species

    def attempt_speciation_with_pressure(
        self,
        genome_ids: List[str],
        current_cycle: int,
        *,
        niche: str = "general",
        base_strength: float = 0.08,
        max_rounds: int = 6,
        strength_step: float = 0.04,
    ) -> tuple[List[str], float]:
        """
        Apply escalating niche pressure until divergence crosses threshold or rounds exhaust.
        Returns (new_species_ids, final_measured_divergence).
        """
        measured = self.measure_group_divergence(genome_ids)
        for round_idx in range(max_rounds):
            new_sp = self.attempt_speciation(genome_ids, current_cycle, niche=niche)
            measured = self.measure_group_divergence(genome_ids)
            if new_sp:
                return new_sp, measured
            strength = base_strength + round_idx * strength_step
            self.apply_divergence_pressure(genome_ids, strength=strength)
            measured = self.measure_group_divergence(genome_ids)
        return [], measured

    def apply_divergence_pressure(self, genome_ids: List[str], strength: float = 0.1):
        """Simulate different niches pushing traits apart (used in experiments)."""
        if len(genome_ids) < 2:
            return
        for i, gid in enumerate(genome_ids):
            if gid not in self.substrate.genomes:
                continue
            dna = self.substrate.genomes[gid].dna
            traits = dna.get_traits()
            # Push some traits in opposite directions for demo
            factor = 1 if i % 2 == 0 else -1
            for k in ["novelty_seeking", "math", "alignment"]:
                if k in traits:
                    traits[k] = max(0.1, min(0.95, traits[k] + factor * strength))
            dna.traits.update(traits)

    def get_species_for_genome(self, gid: str) -> Optional[str]:
        if gid in self.substrate.genomes:
            dna = self.substrate.genomes[gid].dna
            return getattr(dna, 'species_id', 'ROOT')
        return None

    def should_isolate(self, gid1: str, gid2: str) -> bool:
        """High divergence → no memetic/crossover between them."""
        if gid1 not in self.substrate.genomes or gid2 not in self.substrate.genomes:
            return False
        d1 = self.substrate.genomes[gid1].dna
        d2 = self.substrate.genomes[gid2].dna
        return self.calculate_divergence(d1, d2) > self.divergence_threshold * 1.5

    def summary(self) -> Dict[str, Any]:
        return {
            "num_species": len(self.species),
            "num_events": len(self.events),
            "latest_event": asdict(self.events[-1]) if self.events else None,
            "species": {k: asdict(v) for k, v in list(self.species.items())[-5:]},
        }


_speciation_engine: Optional[SpeciationEngine] = None

def get_speciation_engine() -> SpeciationEngine:
    global _speciation_engine
    if _speciation_engine is None:
        _speciation_engine = SpeciationEngine()
    return _speciation_engine


def render_phylogeny_ascii(
    events: List[SpeciationEvent] | None = None,
    *,
    root: str = "ROOT",
) -> str:
    """
    Render a simple ASCII phylogenetic tree from speciation events.

    Example (demo species from speciation_phase):
        ROOT
        ├── DEMO-SPECIES-01  (Experiment 1)
        └── DEMO-SPECIES-05  (Experiment 5)
    """
    engine = get_speciation_engine()
    evts = events if events is not None else engine.events
    if not evts:
        return f"{root}\n  (no speciation events yet)"

    children: Dict[str, List[tuple[str, str]]] = {}
    for evt in evts:
        parent = evt.parent_species or root
        label = evt.new_species
        if evt.trigger == "high_pairwise_divergence":
            label = f"{label}  (divergence={evt.divergence:.2f})"
        children.setdefault(parent, []).append((evt.new_species, label))

    lines = [root]

    def _walk(parent: str, prefix: str, is_last: bool) -> None:
        kids = children.get(parent, [])
        for i, (_sid, display) in enumerate(kids):
            last = i == len(kids) - 1
            branch = "└── " if last else "├── "
            lines.append(f"{prefix}{branch}{display}")
            extension = "    " if last else "│   "
            _walk(_sid, prefix + extension, last)

    _walk(root, "", True)
    return "\n".join(lines)
