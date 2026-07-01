"""GenomicSubstrate v1 — living registry of OmniDNA, queryable by capability."""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oss.dna.omni_dna import OmniDNA
from oss.schemas.genome import DNAType, Trait
from oss.substrate.attention_config import AttentionConfig, traits_to_vector

GenomeId = str

_REPO = Path(__file__).resolve().parents[2]
_FITNESS_PATH = _REPO / "data" / "genomic_fitness.jsonl"
_LINEAGE_PATH = _REPO / "data" / "genomic_lineage.json"


@dataclass(frozen=True)
class CapabilityDescriptor:
    domain: str
    skill: str
    min_level: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {"domain": self.domain, "skill": self.skill, "min_level": self.min_level}


@dataclass
class GenomeSegment:
    """Subset of traits/memes/qualia + metadata — not a file."""

    genome_id: GenomeId
    capabilities: tuple[str, ...]
    domains: tuple[str, ...]
    traits: dict[str, float]
    qualia: dict[str, float] = field(default_factory=dict)
    role: str = ""
    fitness: float = 0.0
    generation: int = 0
    attention_config: "AttentionConfig | None" = field(default=None, compare=False)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "genome_id": self.genome_id,
            "capabilities": list(self.capabilities),
            "domains": list(self.domains),
            "traits": self.traits,
            "qualia": {k: round(v, 4) for k, v in self.qualia.items()},
            "role": self.role,
            "fitness": round(self.fitness, 4),
            "generation": self.generation,
        }
        if self.attention_config is not None:
            d["attention_config"] = self.attention_config.to_dict()
        return d

    def trait_vector(self) -> "np.ndarray":
        """Return the canonical 32-D trait vector for this genome segment."""
        import numpy as np  # local import — substrate is numpy-optional at import time
        return traits_to_vector(self.traits)


@dataclass
class AgentHandle:
    """Spawned agent — DNA + role embodiment handle."""

    genome_id: GenomeId
    role: str
    agent_id: str
    display_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "role": self.role,
            "agent_id": self.agent_id,
            "display_name": self.display_name,
        }


# domain + skill → trait keys used for capability scoring
_SKILL_TRAIT_MAP: dict[tuple[str, str], tuple[str, ...]] = {
    ("physics", "theorizing"): ("research", "analysis", "math", "curiosity"),
    ("markets", "strategy_design"): ("pattern_detection", "risk_tolerance", "market_intuition", "finance", "strategy"),
    ("markets", "risk_modeling"): ("risk", "finance", "strategy", "analysis"),
    ("science", "theorizing"): ("research", "analysis", "math", "curiosity"),
    ("infra", "operations"): ("coding", "ops", "systems", "reliability"),
    ("governance", "alignment"): ("safety", "ethics", "audit", "compliance"),
    ("product", "building"): ("design", "growth", "monetization", "ux"),
    ("product", "creativity"): ("creativity", "empathy", "market_intuition", "innovation", "design"),
}

_CAPABILITY_MAP: dict[str, tuple[str, ...]] = {
    "scientific_theorizing": ("research", "analysis", "math", "curiosity"),
    "strategy_design": ("pattern_detection", "risk_tolerance", "market_intuition", "finance", "strategy"),
    "market_allocation": ("risk", "finance", "strategy", "economics"),
    "infra_operations": ("coding", "ops", "systems", "reliability"),
    "governance_alignment": ("safety", "ethics", "audit", "compliance"),
    "product_building": ("design", "growth", "monetization", "ux"),
    "product_creativity": ("creativity", "empathy", "market_intuition", "innovation", "design"),
}

_ROLE_PERSONA: dict[str, str] = {
    "scientist": "ORACLE",
    "investor": "AVERY",
    "operator": "FORGE",
    "governor": "SENTINEL",
    "builder": "NEXUS",
}


class GenomicSubstrate:
    """
    Living registry — not a filesystem, not static code.

    Query by capability/traits; mutate via evolution operations.
    """

    def __init__(self) -> None:
        self._genomes: dict[GenomeId, OmniDNA] = {}
        self._fitness: dict[GenomeId, list[dict[str, Any]]] = {}
        self._lineage: dict[GenomeId, dict[str, Any]] = {}
        self._load_persisted()

    # ── 1. Register / store ───────────────────────────────────────────────

    def register_genome(self, dna: OmniDNA) -> GenomeId:
        gid = dna.genome_id or dna.unique_id
        dna.genome_id = gid
        self._genomes[gid] = dna
        if gid not in self._lineage:
            self._lineage[gid] = {
                "genome_id": gid,
                "parent_id": dna.parent_id,
                "children": [],
                "generation": dna.generation,
                "created_ts": time.time(),
            }
        return gid

    def register(self, dna: OmniDNA) -> GenomeId:
        """Alias for register_genome (backward compat)."""
        return self.register_genome(dna)

    def update_genome(self, genome_id: GenomeId, dna: OmniDNA) -> None:
        if genome_id not in self._genomes:
            raise KeyError(f"Unknown genome: {genome_id}")
        dna.genome_id = genome_id
        self._genomes[genome_id] = dna

    def get_genome(self, genome_id: GenomeId) -> OmniDNA | None:
        return self._genomes.get(genome_id)

    def load_from_mind(self) -> int:
        from oss.mind.omni_mind import get_mind
        mind = get_mind()
        if not mind.agents:
            mind.bootstrap()
        for dna in mind.agents.values():
            self.register_genome(dna)
        return len(self._genomes)

    # ── 2. Query ──────────────────────────────────────────────────────────

    def query_by_traits(self, required_traits: dict[str, float]) -> list[GenomeId]:
        self._ensure_loaded()
        hits: list[tuple[float, GenomeId]] = []
        for gid, dna in self._genomes.items():
            if all(dna.trait_value(t, 0.0) >= min_v for t, min_v in required_traits.items()):
                avg = sum(dna.trait_value(t, 0) for t in required_traits) / len(required_traits)
                hits.append((avg, gid))
        return [gid for _, gid in sorted(hits, reverse=True)]

    def query_by_capability(self, capability: CapabilityDescriptor) -> list[GenomeId]:
        keys = _SKILL_TRAIT_MAP.get(
            (capability.domain, capability.skill),
            _CAPABILITY_MAP.get(capability.skill, ("general",)),
        )
        self._ensure_loaded()
        hits: list[tuple[float, GenomeId]] = []
        for gid, dna in self._genomes.items():
            score = sum(dna.trait_value(k, 0.3) for k in keys) / max(len(keys), 1)
            seg = self.segment(gid)
            if capability.domain and seg and capability.domain not in seg.domains:
                if capability.domain != "markets" or "economics" not in seg.domains:
                    continue
            if score >= capability.min_level:
                hits.append((score, gid))
        return [gid for _, gid in sorted(hits, reverse=True)]

    def query_by_role(self, role: str) -> list[GenomeId]:
        self._ensure_loaded()
        role_l = role.lower()
        persona = _ROLE_PERSONA.get(role_l, role.upper())
        return [
            gid for gid, dna in self._genomes.items()
            if dna.registry_agent_id.upper() == persona.upper()
            or str(dna.meta_dna.get("species_role", "")).lower() == role_l
        ]

    def query(
        self,
        *,
        capability: str = "",
        domain: str = "",
        min_trait: str = "",
        min_value: float = 0.0,
    ) -> list[GenomeSegment]:
        """Backward-compat segment query."""
        self._ensure_loaded()
        if capability and domain:
            ids = self.query_by_capability(CapabilityDescriptor(domain, capability, min_value or 0.35))
        elif capability:
            ids = self.query_by_traits({min_trait or "fitness": min_value}) if min_trait else [
                gid for gid in self._genomes
                if capability in (self.segment(gid).capabilities if self.segment(gid) else ())
            ]
        else:
            ids = list(self._genomes.keys())
        results = [self.segment(gid) for gid in ids if self.segment(gid)]
        if min_trait:
            results = [s for s in results if s.traits.get(min_trait, 0) >= min_value]
        return sorted(results, key=lambda s: s.fitness, reverse=True)

    def segment(self, genome_id: GenomeId) -> GenomeSegment | None:
        dna = self._genomes.get(genome_id)
        if not dna:
            return None
        traits = {k: round(t.value, 4) for k, t in dna.traits.items()}
        attn_cfg = AttentionConfig.from_genome_traits(traits, genome_id=genome_id)
        return GenomeSegment(
            genome_id=genome_id,
            capabilities=self._infer_capabilities(traits),
            domains=self._infer_domains(dna),
            traits=traits,
            qualia={k: round(v, 4) for k, v in dna.qualia.items()},
            role=str(dna.meta_dna.get("species_role", "")),
            fitness=self._mean_fitness(genome_id),
            generation=dna.generation,
            attention_config=attn_cfg,
        )

    def get_attention_module(self, genome_id: GenomeId):
        """
        Build and return an MA_INBLAttention module tuned to this genome's traits.

        The module's hyperparameters (temperature, max_growth, training_binary_ratio)
        are derived deterministically from the genome's trait values and genome_id.
        """
        seg = self.segment(genome_id)
        if seg is None:
            raise KeyError(f"Genome not found: {genome_id}")
        if seg.attention_config is None:
            from oss.substrate.attention_config import AttentionConfig
            cfg = AttentionConfig.from_genome_traits(seg.traits, genome_id=genome_id)
        else:
            cfg = seg.attention_config
        return cfg.build_module()

    def build_model(self, genome_id: GenomeId, *, num_layers: int = 2):
        """
        Build a full SubstrateModel (stacked MA_INBLAttention blocks) tuned to
        this genome's trait profile.

        num_layers : number of transformer blocks (default 2)
        Returns    : SubstrateTransformer ready for encode() / score_candidates()
        """
        seg = self.segment(genome_id)
        if seg is None:
            raise KeyError(f"Genome not found: {genome_id}")
        cfg = seg.attention_config or AttentionConfig.from_genome_traits(
            seg.traits, genome_id=genome_id
        )
        from oss.substrate.transformer import SubstrateTransformer
        return SubstrateTransformer.from_attention_config(cfg, num_layers=num_layers)

    def count(self) -> int:
        return len(self._genomes)

    # ── 3. Evolution operations ───────────────────────────────────────────

    def mutate(self, genome_id: GenomeId, intensity: float = 0.1) -> OmniDNA:
        dna = self._require(genome_id)
        score = max(0.0, min(1.0, 0.5 + random.uniform(-intensity, intensity)))
        for trait in dna.traits.values():
            trait.value = max(0.0, min(1.0, trait.value + random.uniform(-intensity, intensity)))
        dna.evolve(score=score)
        self.update_genome(genome_id, dna)
        return dna

    def crossover(self, parent_a: GenomeId, parent_b: GenomeId) -> tuple[OmniDNA, OmniDNA]:
        a = self._require(parent_a)
        b = self._require(parent_b)
        child1 = self._child_from_parents(a, b, suffix="a")
        child2 = self._child_from_parents(b, a, suffix="b")
        id1 = self.register_genome(child1)
        id2 = self.register_genome(child2)
        for pid, cid in ((parent_a, id1), (parent_b, id2)):
            if pid in self._lineage:
                self._lineage[pid].setdefault("children", []).append(cid)
        return child1, child2

    def transmute(self, genome_id: GenomeId, input_traits: list[str]) -> bool:
        dna = self._require(genome_id)
        ok = dna.transmute_traits(input_traits)
        if ok:
            self.update_genome(genome_id, dna)
        return ok

    # ── 4. Spawn agents ─────────────────────────────────────────────────────

    def spawn_agent(self, genome_id: GenomeId, role: str) -> AgentHandle:
        from oss.integration.embodiment import AgentEmbodiment
        from oss.substrate.species_registry import get_species_registry

        dna = self._require(genome_id)
        schema = get_species_registry().get_role(role.lower())
        if not schema:
            raise ValueError(f"Unknown role: {role}")
        dna.meta_dna["species_role"] = role.lower()
        AgentEmbodiment(dna=dna, role=schema)  # binds role context
        self.update_genome(genome_id, dna)
        return AgentHandle(
            genome_id=genome_id,
            role=role.lower(),
            agent_id=dna.registry_agent_id,
            display_name=dna.display_name or schema.title,
        )

    # ── 5. Fitness & lineage ────────────────────────────────────────────────

    def record_fitness(
        self,
        genome_id: GenomeId,
        score: float,
        context: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "score": round(float(score), 4),
            "context": context or {},
            "ts": time.time(),
        }
        self._fitness.setdefault(genome_id, []).append(entry)
        if len(self._fitness[genome_id]) > 100:
            self._fitness[genome_id] = self._fitness[genome_id][-100:]
        dna = self._genomes.get(genome_id)
        if dna:
            dna.meta_dna["last_fitness"] = score
            dna.meta_dna["mean_fitness"] = self._mean_fitness(genome_id)
        self._append_fitness_log(genome_id, entry)
        self._save_lineage()

    def get_lineage(self, genome_id: GenomeId) -> list[GenomeId]:
        chain: list[GenomeId] = []
        current = genome_id
        seen: set[str] = set()
        while current and current not in seen:
            seen.add(current)
            chain.append(current)
            meta = self._lineage.get(current, {})
            parent = meta.get("parent_id") or (
                self._genomes[current].parent_id if current in self._genomes else None
            )
            current = parent or ""
        descendants: list[GenomeId] = []
        meta = self._lineage.get(genome_id, {})
        for child in meta.get("children", []):
            descendants.extend(self.get_lineage(child))
        return chain + [c for c in descendants if c not in chain]

    def fitness_history(self, genome_id: GenomeId) -> list[dict[str, Any]]:
        return list(self._fitness.get(genome_id, []))

    # ── internals ───────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        if not self._genomes:
            self.load_from_mind()

    def _require(self, genome_id: GenomeId) -> OmniDNA:
        dna = self._genomes.get(genome_id)
        if not dna:
            raise KeyError(f"Genome not found: {genome_id}")
        return dna

    def _mean_fitness(self, genome_id: GenomeId) -> float:
        hist = self._fitness.get(genome_id, [])
        if not hist:
            dna = self._genomes.get(genome_id)
            return float(dna.meta_dna.get("last_fitness", 0.5)) if dna else 0.5
        return sum(h["score"] for h in hist) / len(hist)

    def _child_from_parents(self, primary: OmniDNA, secondary: OmniDNA, *, suffix: str) -> OmniDNA:
        child = OmniDNA(
            registry_agent_id=primary.registry_agent_id,
            display_name=f"{primary.display_name or 'genome'}-x-{suffix}",
            dna_type=primary.dna_type,
            parent_id=primary.genome_id,
            generation=max(primary.generation, secondary.generation) + 1,
            qualia={k: (primary.qualia.get(k, 0) + secondary.qualia.get(k, 0)) / 2 for k in primary.qualia},
        )
        all_traits = set(primary.traits) | set(secondary.traits)
        for name in all_traits:
            if name in primary.traits and name in secondary.traits:
                v = random.choice([primary.traits[name].value, secondary.traits[name].value])
            elif name in primary.traits:
                v = primary.traits[name].value
            else:
                v = secondary.traits[name].value
            child.add_trait(name, v, primary.traits.get(name, Trait(name, 0.5)).dna_type)
        child.transmutation_recipes = dict(primary.transmutation_recipes)
        child.meta_dna = {"species_role": primary.meta_dna.get("species_role", "investor")}
        return child

    def _infer_capabilities(self, traits: dict[str, float]) -> tuple[str, ...]:
        caps: list[str] = []
        for cap, keys in _CAPABILITY_MAP.items():
            score = sum(traits.get(k, 0.3) for k in keys) / max(len(keys), 1)
            if score >= 0.35:
                caps.append(cap)
        return tuple(caps) or ("general_cognition",)

    def _infer_domains(self, dna: OmniDNA) -> tuple[str, ...]:
        rid = dna.registry_agent_id.upper()
        mapping = {
            "ORACLE": ("science", "physics", "research"),
            "AVERY": ("economics", "markets"),
            "FORGE": ("infra", "code"),
            "SENTINEL": ("governance", "safety"),
            "NEXUS": ("product", "growth"),
            "GH05T3": ("general", "orchestration"),
        }
        return mapping.get(rid, ("general",))

    def _load_persisted(self) -> None:
        if _LINEAGE_PATH.exists():
            try:
                self._lineage = json.loads(_LINEAGE_PATH.read_text(encoding="utf-8"))
            except Exception:
                self._lineage = {}

    def _save_lineage(self) -> None:
        _LINEAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LINEAGE_PATH.write_text(json.dumps(self._lineage, indent=2), encoding="utf-8")

    def _append_fitness_log(self, genome_id: GenomeId, entry: dict[str, Any]) -> None:
        _FITNESS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_FITNESS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"genome_id": genome_id, **entry}) + "\n")

    def status(self) -> dict[str, Any]:
        self._ensure_loaded()
        return {
            "genomes": self.count(),
            "fitness_records": sum(len(v) for v in self._fitness.values()),
            "lineage_nodes": len(self._lineage),
            "api": [
                "register_genome", "update_genome", "query_by_traits",
                "query_by_capability", "query_by_role", "mutate", "crossover",
                "transmute", "spawn_agent", "record_fitness", "get_lineage",
            ],
        }


_substrate: GenomicSubstrate | None = None


def get_genomic_substrate() -> GenomicSubstrate:
    global _substrate
    if _substrate is None:
        _substrate = GenomicSubstrate()
        _substrate.load_from_mind()
    return _substrate


def reset_genomic_substrate() -> None:
    """Clear singleton — for tests and lab isolation."""
    global _substrate
    _substrate = None


def query_genome(*, capability: str, domain: str = "") -> list[dict[str, Any]]:
    sub = get_genomic_substrate()
    if domain:
        ids = sub.query_by_capability(CapabilityDescriptor(domain, capability, 0.35))
        return [sub.segment(gid).to_dict() for gid in ids if sub.segment(gid)]
    return [s.to_dict() for s in sub.query(capability=capability)]