"""Omni Forge — training shard schemas for agency-driven fine-tuning."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ForgeDomain(str, Enum):
    """Knowledge domains the agency layer curates."""

    SECURITY = "security"
    CODE = "code"
    RESEARCH = "research"
    OPS = "ops"
    DATA_SCIENCE = "data_science"
    COMPUTER_SCIENCE = "computer_science"
    FUNGI_ECONOMICS = "fungi_economics"
    THEORETICAL_SCIENCE = "theoretical_science"
    UNKNOWN = "unknown"
    DEFAULT = "default"


class QualityTier(str, Enum):
    TRASH = "trash"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


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
        return cls(
            shard_id=data["shard_id"],
            domain=ForgeDomain(data.get("domain", "default")),
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
            "domains": self.domains,
            "agent_id": self.agent_id,
            "status": self.status,
            "notes": self.notes,
        }