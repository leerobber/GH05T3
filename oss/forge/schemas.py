"""Omni Forge — training shard schemas for agency-driven fine-tuning."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ForgeDomain(str, Enum):
    """Scientific research domains — foundational + Elite AI/ML breed."""

    # Foundational sciences
    CYBER_DEFENSE_SCIENCE = "cyber_defense_science"
    COMPUTATIONAL_SCIENCE = "computational_science"
    EPISTEMOLOGY_AND_DISCOVERY = "epistemology_and_discovery"
    SYSTEMS_ENGINEERING = "systems_engineering"
    STATISTICAL_INFERENCE_SCIENCE = "statistical_inference_science"
    THEORETICAL_COMPUTER_SCIENCE = "theoretical_computer_science"
    MYCOLOGICAL_NETWORK_ECONOMICS = "mycological_network_economics"
    THEORETICAL_PHYSICS_AND_COMPLEXITY = "theoretical_physics_and_complexity"
    FRONTIER_UNKNOWN_SCIENCES = "frontier_unknown_sciences"
    GENERAL_COGNITION = "general_cognition"
    # Elite AI/ML research (new breed)
    MACHINE_LEARNING_THEORY = "machine_learning_theory"
    DEEP_LEARNING_ARCHITECTURES = "deep_learning_architectures"
    NEURAL_SYMBOLIC_INTEGRATION = "neural_symbolic_integration"
    EVOLUTIONARY_COMPUTATION = "evolutionary_computation"
    GENOMICS_INSPIRED_AI = "genomics_inspired_ai"
    COGNITIVE_NEUROSCIENCE = "cognitive_neuroscience"
    QUANTUM_MACHINE_LEARNING = "quantum_machine_learning"
    ALIGNMENT_AND_SAFETY_SCIENCE = "alignment_and_safety_science"
    MULTIMODAL_REPRESENTATION_LEARNING = "multimodal_representation_learning"
    AGENTIC_SYSTEMS_SCIENCE = "agentic_systems_science"


class QualityTier(str, Enum):
    TRASH = "trash"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    ELITE = "elite"


class TrainingParadigm(str, Enum):
    """Training methods — OmniStrand exceeds naive LoRA via genetic density."""

    LORA_SFT = "lora_sft"
    OMNI_STRAND_SFT = "omni_strand_sft"
    GENETIC_DISTILLATION = "genetic_distillation"
    DOMAIN_MOE_ROUTING = "domain_moe_routing"


@dataclass
class QualityVerdict:
    score: float
    tier: QualityTier
    signals: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    keep: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "tier": self.tier.value,
            "signals": {k: round(v, 4) for k, v in self.signals.items()},
            "reasons": self.reasons,
            "keep": self.keep,
        }


@dataclass
class MethylationProfile:
    """Epigenetic quality marks — weight training strands biologically."""

    H3K4me3: float = 0.0   # active transcription (high quality)
    H3K27me3: float = 0.0  # silencing (low priority)
    DNAm: float = 0.0      # methylation stability

    def transcription_weight(self) -> float:
        return max(0.1, 1.0 + self.H3K4me3 * 2.0 - self.H3K27me3 - self.DNAm * 0.5)

    def to_dict(self) -> dict[str, float]:
        return {
            "H3K4me3": round(self.H3K4me3, 4),
            "H3K27me3": round(self.H3K27me3, 4),
            "DNAm": round(self.DNAm, 4),
            "transcription_weight": round(self.transcription_weight(), 3),
        }


@dataclass
class OmniStrand:
    """
    One genetically selected training strand.

    OmniStrand SFT targets 8B–12B param models with effective 100B+ capability via:
    - elite example density (top genetic fitness per domain)
    - methylation-weighted loss (not uniform LoRA rank)
    - domain MoE routing at inference (expert activation, not param scale)
    """

    strand_id: str
    shard_id: str
    domain: ForgeDomain
    chatml: str
    genome_id: str
    fitness: float
    methylation: MethylationProfile
    paradigm: TrainingParadigm = TrainingParadigm.OMNI_STRAND_SFT
    capability_amplifier: float = 1.0
    crispr_targets: list[str] = field(default_factory=list)
    attention_config: dict[str, Any] | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "strand_id": self.strand_id,
            "shard_id": self.shard_id,
            "domain": self.domain.value,
            "chatml": self.chatml,
            "genome_id": self.genome_id,
            "fitness": round(self.fitness, 4),
            "methylation": self.methylation.to_dict(),
            "paradigm": self.paradigm.value,
            "capability_amplifier": round(self.capability_amplifier, 2),
            "crispr_targets": self.crispr_targets,
            "training_method": "omni_strand_sft",
        }
        if self.attention_config is not None:
            d["attention_config"] = self.attention_config
        return d


@dataclass
class EliteBreedProfile:
    """
    Target profile: small param count, large effective capability.

    8B–12B physical params × genetic density × domain MoE routing
    → effective capability equivalent to 100B+ monolith on breadth tasks.
    """

    physical_params_b: float = 8.0
    target_effective_params_b: float = 100.0
    paradigm: TrainingParadigm = TrainingParadigm.OMNI_STRAND_SFT
    elite_domains: list[str] = field(default_factory=list)
    strand_count: int = 0
    mean_fitness: float = 0.0
    amplification_factor: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "physical_params_b": self.physical_params_b,
            "target_effective_params_b": self.target_effective_params_b,
            "paradigm": self.paradigm.value,
            "elite_domains": self.elite_domains,
            "strand_count": self.strand_count,
            "mean_fitness": round(self.mean_fitness, 4),
            "amplification_factor": round(self.amplification_factor, 2),
            "effective_capability_b": round(
                self.physical_params_b * self.amplification_factor, 1
            ),
        }


@dataclass
class TrainingShard:
    """One curatable training example with provenance."""

    shard_id: str
    domain: ForgeDomain
    system: str
    user: str
    assistant: str
    source: str
    genome_id: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def text_len(self) -> int:
        return len(self.system) + len(self.user) + len(self.assistant)

    def to_dict(self) -> dict[str, Any]:
        return {
            "shard_id": self.shard_id,
            "domain": self.domain.value,
            "system": self.system,
            "user": self.user,
            "assistant": self.assistant,
            "source": self.source,
            "genome_id": self.genome_id,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingShard:
        from oss.forge.domains import resolve_domain
        return cls(
            shard_id=data["shard_id"],
            domain=resolve_domain(data.get("domain", "general_cognition")),
            system=data.get("system", ""),
            user=data.get("user", ""),
            assistant=data.get("assistant", ""),
            source=data.get("source", "unknown"),
            genome_id=data.get("genome_id", ""),
            tags=list(data.get("tags") or []),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class ForgeRunRecord:
    """One agency curation cycle."""

    run_id: str
    ingested: int = 0
    kept: int = 0
    trashed: int = 0
    exported: int = 0
    elite_strands: int = 0
    domains: dict[str, int] = field(default_factory=dict)
    agent_id: str = "forge"
    status: str = "pending"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "ingested": self.ingested,
            "kept": self.kept,
            "trashed": self.trashed,
            "exported": self.exported,
            "elite_strands": self.elite_strands,
            "domains": self.domains,
            "agent_id": self.agent_id,
            "status": self.status,
            "notes": self.notes,
        }