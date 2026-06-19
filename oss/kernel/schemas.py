"""Civilization Kernel — self-sustaining intelligence state contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Pillar(str, Enum):
    SCIENCE = "theory_engine"
    FINANCE = "finance_engine"
    EXECUTION = "operations_engine"
    GOVERNANCE = "constitution_engine"


class HeartbeatPhase(str, Enum):
    RESEARCH = "research"
    MONETIZE = "monetize"
    TREASURY = "treasury"
    INVEST = "invest"
    FUND = "fund"
    IMPROVE = "improve"
    GOVERN = "govern"


class DataTerritoryClass(str, Enum):
    STRUCTURED_SCIENCE = "structured_science"
    UNSTRUCTURED_EXOTIC = "unstructured_exotic"
    SYNTHETIC = "synthetic"
    ECONOMIC = "economic"
    AGENT_SIM = "agent_simulation"


@dataclass
class DataTerritory:
    key: str
    title: str
    territory_class: DataTerritoryClass
    forge_domain: str = ""
    ingest_paths: tuple[str, ...] = ()
    synthetic: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "class": self.territory_class.value,
            "forge_domain": self.forge_domain,
            "ingest_paths": list(self.ingest_paths),
            "synthetic": self.synthetic,
        }


@dataclass
class TreasuryPolicy:
    reserve_pct: float = 0.25
    research_pct: float = 0.35
    compute_pct: float = 0.25
    agent_payroll_pct: float = 0.10
    risk_buffer_pct: float = 0.05

    def validate(self) -> None:
        total = (
            self.reserve_pct + self.research_pct + self.compute_pct
            + self.agent_payroll_pct + self.risk_buffer_pct
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Treasury allocations must sum to 1.0, got {total:.3f}")


@dataclass
class PhaseResult:
    phase: HeartbeatPhase
    pillar: Pillar
    ok: bool
    summary: str
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase.value,
            "pillar": self.pillar.value,
            "ok": self.ok,
            "summary": self.summary,
            "metrics": self.metrics,
        }


@dataclass
class TickResult:
    tick: int
    dry_run: bool
    phases: list[PhaseResult]
    treasury_balance: float = 0.0
    blocked: bool = False
    block_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "dry_run": self.dry_run,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "treasury_balance": round(self.treasury_balance, 4),
            "phases": [p.to_dict() for p in self.phases],
            "all_ok": all(p.ok for p in self.phases) and not self.blocked,
        }


@dataclass
class KernelState:
    tick: int = 0
    last_domain: str = "business"
    cumulative_revenue: float = 0.0
    cumulative_research_runs: int = 0
    last_tick_ts: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "last_domain": self.last_domain,
            "cumulative_revenue": round(self.cumulative_revenue, 4),
            "cumulative_research_runs": self.cumulative_research_runs,
            "last_tick_ts": self.last_tick_ts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KernelState:
        return cls(
            tick=int(data.get("tick", 0)),
            last_domain=str(data.get("last_domain", "business")),
            cumulative_revenue=float(data.get("cumulative_revenue", 0.0)),
            cumulative_research_runs=int(data.get("cumulative_research_runs", 0)),
            last_tick_ts=float(data.get("last_tick_ts", 0.0)),
        )