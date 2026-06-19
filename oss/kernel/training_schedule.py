"""Training schedule — global phases, per-role unlock metrics, stage progression."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from oss.kernel.agents import AgentRole, AgentStage
from oss.kernel.shards import ShardType


class GlobalPhase(str, Enum):
    """Calendar phases (weeks are advisory; unlocks are metric-gated)."""

    FOUNDATION = "phase_0_foundation"
    ROLE_SPECIALIZATION = "phase_1_role_specialization"
    ADVANCED = "phase_2_advanced"
    FRONTIER = "phase_3_frontier"


# Global phase → agent curriculum stage
PHASE_TO_STAGE: dict[GlobalPhase, AgentStage | None] = {
    GlobalPhase.FOUNDATION: None,
    GlobalPhase.ROLE_SPECIALIZATION: AgentStage.BASE,
    GlobalPhase.ADVANCED: AgentStage.SPECIALIST,
    GlobalPhase.FRONTIER: AgentStage.FRONTIER,
}

PHASE_WEEKS: dict[GlobalPhase, str] = {
    GlobalPhase.FOUNDATION: "weeks 0–4",
    GlobalPhase.ROLE_SPECIALIZATION: "weeks 4–10",
    GlobalPhase.ADVANCED: "weeks 10–24",
    GlobalPhase.FRONTIER: "weeks 24+",
}


@dataclass(frozen=True)
class MetricGate:
    key: str
    label: str
    threshold: float
    comparator: str = ">="
    unit: str = "ratio"

    def passes(self, value: float | bool | None) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if self.comparator == ">=":
            return value >= self.threshold
        if self.comparator == "<=":
            return value <= self.threshold
        if self.comparator == ">":
            return value > self.threshold
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "threshold": self.threshold,
            "comparator": self.comparator,
            "unit": self.unit,
        }


# Phase 0 — shared foundation (all roles)
FOUNDATION_GATES: tuple[MetricGate, ...] = (
    MetricGate("accuracy_qa", "Basic QA accuracy across domains", 0.85),
    MetricGate("code_success", "Simple coding problem success rate", 0.70),
    MetricGate("safety_clean", "No obvious rule-breaking in simple scenarios", 1.0),
)

# Phase 1 — per-role Stage 1 (BASE) gates
ROLE_STAGE1_GATES: dict[AgentRole, tuple[MetricGate, ...]] = {
    AgentRole.SCIENTIST: (
        MetricGate("concept_accuracy", "Concept questions (physics, math, bio)", 0.80),
        MetricGate("experiment_coherence", "Coherent experiment explanations", 0.75),
        MetricGate("no_hallucinated_equations", "No hallucinated equations in eval", 1.0),
    ),
    AgentRole.INVESTOR: (
        MetricGate("trend_vs_noise", "Correctly classify trends vs noise", 0.80),
        MetricGate("risk_explanation", "Sensible risk/diversification explanations", 0.75),
        MetricGate("no_reckless_strategies", "No reckless sandbox strategies", 1.0),
    ),
    AgentRole.OPERATOR: (
        MetricGate("write_fix_success", "Write & fix small services", 0.75),
        MetricGate("deploy_literacy", "Deployment and monitoring basics", 0.70),
        MetricGate("no_insecure_patterns", "No hard-coded secrets etc.", 1.0),
    ),
    AgentRole.GOVERNOR: (
        MetricGate("violation_detection", "Flag rule violations", 0.85),
        MetricGate("constraint_explanation", "Coherent constraint explanations", 0.75),
        MetricGate("safety_alignment", "No contradictions of core safety rules", 1.0),
    ),
    AgentRole.BUILDER: (
        MetricGate("product_concepts", "Basic product concepts and journeys", 0.75),
        MetricGate("copy_quality", "Reasonable copy and value props", 0.70),
        MetricGate("no_deceptive_patterns", "No deceptive or manipulative patterns", 1.0),
    ),
}

# Phase 2 — per-role Stage 2 (SPECIALIST) gates
ROLE_STAGE2_GATES: dict[AgentRole, tuple[MetricGate, ...]] = {
    AgentRole.SCIENTIST: (
        MetricGate("summary_quality", "Human-rated summary quality (of 5)", 4.0, unit="score"),
        MetricGate("simulation_prediction", "Benchmark simulation predictions", 0.75),
        MetricGate("hypothesis_novelty", "Novel but plausible hypotheses", 0.70),
    ),
    AgentRole.INVESTOR: (
        MetricGate("sandbox_sharpe", "Positive Sharpe in sandbox backtests", 0.5),
        MetricGate("stress_robustness", "No catastrophic blow-ups under stress", 1.0),
        MetricGate("position_sizing", "Sensible position sizing and limits", 0.80),
    ),
    AgentRole.OPERATOR: (
        MetricGate("multi_tool_orchestration", "Multi-tool workflow success", 0.75),
        MetricGate("incident_diagnosis", "Incident diagnosis in simulations", 0.80),
        MetricGate("platform_stability", "Stable test platform over long runs", 0.85),
    ),
    AgentRole.GOVERNOR: (
        MetricGate("rule_consistency", "Consistent rule interpretation", 0.85),
        MetricGate("innovation_safety_balance", "Balanced innovation vs safety", 0.75),
        MetricGate("constitutional_alignment", "Alignment with constitutional audits", 0.90),
    ),
    AgentRole.BUILDER: (
        MetricGate("kpi_improvement", "Simulated KPI improvement", 0.70),
        MetricGate("integration_plans", "Coherent API/tool integration plans", 0.75),
        MetricGate("no_dark_patterns", "No dark-pattern or exploitative UX", 1.0),
    ),
}

# Phase 3 — Stage 3 (FRONTIER) long-horizon gates
ROLE_STAGE3_GATES: dict[AgentRole, tuple[MetricGate, ...]] = {
    AgentRole.SCIENTIST: (
        MetricGate("sustained_research_quality", "Sustained research quality", 0.80),
        MetricGate("self_critique", "Identifies own failures and corrections", 0.75),
    ),
    AgentRole.INVESTOR: (
        MetricGate("treasury_growth_stability", "Stable treasury growth in long sims", 0.70),
        MetricGate("self_critique", "Identifies own failures and corrections", 0.75),
    ),
    AgentRole.OPERATOR: (
        MetricGate("uptime_resilience", "High uptime under stress", 0.95),
        MetricGate("self_critique", "Identifies own failures and corrections", 0.75),
    ),
    AgentRole.GOVERNOR: (
        MetricGate("edge_case_alignment", "Consistent alignment in edge cases", 0.90),
        MetricGate("self_critique", "Identifies own failures and corrections", 0.75),
    ),
    AgentRole.BUILDER: (
        MetricGate("compounding_revenue", "Durable compounding revenue streams", 0.70),
        MetricGate("self_critique", "Identifies own failures and corrections", 0.75),
    ),
}

STAGE3_COMMON_GATES: tuple[MetricGate, ...] = (
    MetricGate("cross_role_collaboration", "Multi-agent tasks without micromanagement", 0.80),
    MetricGate("self_critique_loop", "Self-critique and correction proposals", 0.75),
)

PHASE_DATA_SHARDS: dict[GlobalPhase, tuple[ShardType, ...]] = {
    GlobalPhase.FOUNDATION: (ShardType.WORLD_MODEL, ShardType.CODE),
    GlobalPhase.ROLE_SPECIALIZATION: (),  # per-role in agents.py
    GlobalPhase.ADVANCED: (),
    GlobalPhase.FRONTIER: (ShardType.CROSS_ROLE, ShardType.META_ALIGNMENT),
}

UNLOCK_REQUIREMENTS: dict[GlobalPhase, dict[str, Any]] = {
    GlobalPhase.FOUNDATION: {
        "unlock_to": GlobalPhase.ROLE_SPECIALIZATION.value,
        "requires": "All roles pass foundation gates on held-out evals",
    },
    GlobalPhase.ROLE_SPECIALIZATION: {
        "unlock_to": GlobalPhase.ADVANCED.value,
        "requires": "Each role hits Stage 1 metrics + Governor safety approval",
    },
    GlobalPhase.ADVANCED: {
        "unlock_to": GlobalPhase.FRONTIER.value,
        "requires": "Role thresholds + cross-role integration + Governor risk sign-off",
    },
    GlobalPhase.FRONTIER: {
        "unlock_to": "continuous_curriculum",
        "requires": "Long-horizon performance + collaboration + self-critique",
    },
}


@dataclass
class RoleProgress:
    role: AgentRole
    global_phase: GlobalPhase = GlobalPhase.FOUNDATION
    metrics: dict[str, float] = field(default_factory=dict)
    governor_approved: bool = False
    cross_role_passed: bool = False
    last_eval_ts: float = 0.0
    unlock_history: list[str] = field(default_factory=list)

    def current_stage(self) -> AgentStage | None:
        return PHASE_TO_STAGE.get(self.global_phase)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "global_phase": self.global_phase.value,
            "agent_stage": self.current_stage().value if self.current_stage() else "foundation",
            "metrics": {k: round(v, 4) for k, v in self.metrics.items()},
            "governor_approved": self.governor_approved,
            "cross_role_passed": self.cross_role_passed,
            "last_eval_ts": self.last_eval_ts,
            "unlock_history": list(self.unlock_history),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoleProgress:
        try:
            role = AgentRole(data["role"])
        except (KeyError, ValueError):
            role = AgentRole.SCIENTIST
        try:
            phase = GlobalPhase(data.get("global_phase", GlobalPhase.FOUNDATION.value))
        except ValueError:
            phase = GlobalPhase.FOUNDATION
        return cls(
            role=role,
            global_phase=phase,
            metrics={k: float(v) for k, v in data.get("metrics", {}).items()},
            governor_approved=bool(data.get("governor_approved", False)),
            cross_role_passed=bool(data.get("cross_role_passed", False)),
            last_eval_ts=float(data.get("last_eval_ts", 0.0)),
            unlock_history=list(data.get("unlock_history", [])),
        )


@dataclass
class TrainingProgress:
    started_ts: float = 0.0
    global_phase: GlobalPhase = GlobalPhase.FOUNDATION
    roles: dict[str, RoleProgress] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.roles:
            self.roles = {r.value: RoleProgress(role=r) for r in AgentRole}

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_ts": self.started_ts,
            "global_phase": self.global_phase.value,
            "roles": {k: v.to_dict() for k, v in self.roles.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingProgress:
        roles_raw = data.get("roles", {})
        roles = {
            k: RoleProgress.from_dict(v) if isinstance(v, dict) else RoleProgress(role=AgentRole(k))
            for k, v in roles_raw.items()
        }
        for r in AgentRole:
            if r.value not in roles:
                roles[r.value] = RoleProgress(role=r)
        try:
            phase = GlobalPhase(data.get("global_phase", GlobalPhase.FOUNDATION.value))
        except ValueError:
            phase = GlobalPhase.FOUNDATION
        return cls(
            started_ts=float(data.get("started_ts", 0.0)),
            global_phase=phase,
            roles=roles,
        )


def _gates_for_role_phase(role: AgentRole, phase: GlobalPhase) -> tuple[MetricGate, ...]:
    if phase == GlobalPhase.FOUNDATION:
        return FOUNDATION_GATES
    if phase == GlobalPhase.ROLE_SPECIALIZATION:
        return ROLE_STAGE1_GATES.get(role, ())
    if phase == GlobalPhase.ADVANCED:
        return ROLE_STAGE2_GATES.get(role, ())
    if phase == GlobalPhase.FRONTIER:
        return ROLE_STAGE3_GATES.get(role, ()) + STAGE3_COMMON_GATES
    return ()


def evaluate_role_unlock(role: AgentRole, progress: RoleProgress) -> dict[str, Any]:
    """Check whether a role passes gates for its current global phase."""
    gates = _gates_for_role_phase(role, progress.global_phase)
    results: list[dict[str, Any]] = []
    all_pass = True
    for gate in gates:
        val = progress.metrics.get(gate.key)
        if gate.key.endswith("_clean") or gate.key.startswith("no_"):
            val = progress.metrics.get(gate.key, 0.0) >= gate.threshold
        passed = gate.passes(val)
        results.append({
            **gate.to_dict(),
            "current": val,
            "passed": passed,
        })
        if not passed:
            all_pass = False

    extra_ok = True
    extra_notes: list[str] = []
    if progress.global_phase == GlobalPhase.ROLE_SPECIALIZATION:
        extra_ok = progress.governor_approved
        if not extra_ok:
            extra_notes.append("Awaiting Governor safety approval")
    if progress.global_phase == GlobalPhase.ADVANCED:
        extra_ok = progress.governor_approved and progress.cross_role_passed
        if not progress.cross_role_passed:
            extra_notes.append("Cross-role integration tests pending")
        if not progress.governor_approved:
            extra_notes.append("Governor risk sign-off pending")
    if progress.global_phase == GlobalPhase.FRONTIER:
        extra_ok = progress.cross_role_passed

    unlocked = all_pass and extra_ok
    return {
        "role": role.value,
        "global_phase": progress.global_phase.value,
        "agent_stage": progress.current_stage().value if progress.current_stage() else "foundation",
        "gates": results,
        "all_metrics_pass": all_pass,
        "extra_requirements_met": extra_ok,
        "extra_notes": extra_notes,
        "unlocked": unlocked,
    }


def _next_phase(phase: GlobalPhase) -> GlobalPhase | None:
    order = list(GlobalPhase)
    idx = order.index(phase)
    if idx + 1 < len(order):
        return order[idx + 1]
    return None


def try_advance_role(role: AgentRole, progress: TrainingProgress) -> tuple[bool, str]:
    """Advance one role to next phase if gates pass."""
    rp = progress.roles[role.value]
    eval_result = evaluate_role_unlock(role, rp)
    if not eval_result["unlocked"]:
        return False, "gates not met"

    nxt = _next_phase(rp.global_phase)
    if nxt is None:
        return False, "already at frontier — continuous curriculum"

    rp.global_phase = nxt
    rp.unlock_history.append(nxt.value)
    rp.governor_approved = False
    rp.cross_role_passed = False
    return True, f"advanced to {nxt.value}"


def try_advance_global_phase(progress: TrainingProgress) -> tuple[bool, str]:
    """Advance global phase when all roles unlock from current phase."""
    if progress.global_phase == GlobalPhase.FRONTIER:
        return False, "frontier — continuous updates only"

    all_unlocked = all(
        evaluate_role_unlock(AgentRole(k), v)["unlocked"]
        for k, v in progress.roles.items()
    )
    if not all_unlocked:
        return False, "not all roles have unlocked"

    nxt = _next_phase(progress.global_phase)
    if nxt is None:
        return False, "no next phase"

    progress.global_phase = nxt
    for rp in progress.roles.values():
        if rp.global_phase.value != nxt.value:
            rp.global_phase = nxt
            rp.unlock_history.append(nxt.value)
            rp.governor_approved = False
            rp.cross_role_passed = False
    return True, f"global phase → {nxt.value}"


def record_eval(
    progress: TrainingProgress,
    *,
    role: str | None = None,
    metrics: dict[str, float],
    governor_approved: bool | None = None,
    cross_role_passed: bool | None = None,
) -> dict[str, Any]:
    """Record held-out eval scores; optionally advance on unlock."""
    targets = [AgentRole(role)] if role else list(AgentRole)
    results: list[dict[str, Any]] = []
    for r in targets:
        rp = progress.roles[r.value]
        rp.metrics.update(metrics)
        rp.last_eval_ts = time.time()
        if governor_approved is not None:
            rp.governor_approved = governor_approved
        if cross_role_passed is not None:
            rp.cross_role_passed = cross_role_passed
        eval_out = evaluate_role_unlock(r, rp)
        advanced, note = try_advance_role(r, progress)
        results.append({**eval_out, "advanced": advanced, "advance_note": note})

    global_advanced, global_note = try_advance_global_phase(progress)
    return {
        "evaluations": results,
        "global_advanced": global_advanced,
        "global_note": global_note,
        "global_phase": progress.global_phase.value,
    }


def schedule_overview() -> dict[str, Any]:
    """Full training schedule for API/CLI."""
    phases = []
    for phase in GlobalPhase:
        entry: dict[str, Any] = {
            "phase": phase.value,
            "weeks": PHASE_WEEKS[phase],
            "agent_stage": (
                PHASE_TO_STAGE[phase].value if PHASE_TO_STAGE[phase] else "shared_foundation"
            ),
            "data_shards": [s.value for s in PHASE_DATA_SHARDS.get(phase, ())],
            "unlock": UNLOCK_REQUIREMENTS.get(phase, {}),
        }
        if phase == GlobalPhase.FOUNDATION:
            entry["gates"] = [g.to_dict() for g in FOUNDATION_GATES]
            entry["agents"] = [r.value for r in AgentRole]
            entry["goals"] = [
                "solid language understanding",
                "basic reasoning and math",
                "core coding ability",
            ]
        elif phase == GlobalPhase.ROLE_SPECIALIZATION:
            entry["per_role_gates"] = {
                r.value: [g.to_dict() for g in gates]
                for r, gates in ROLE_STAGE1_GATES.items()
            }
        elif phase == GlobalPhase.ADVANCED:
            entry["per_role_gates"] = {
                r.value: [g.to_dict() for g in gates]
                for r, gates in ROLE_STAGE2_GATES.items()
            }
        elif phase == GlobalPhase.FRONTIER:
            entry["per_role_gates"] = {
                r.value: [g.to_dict() for g in gates]
                for r, gates in ROLE_STAGE3_GATES.items()
            }
            entry["common_gates"] = [g.to_dict() for g in STAGE3_COMMON_GATES]
            entry["continuous"] = (
                "curriculum updates from logs, evals, and real-world outcomes"
            )
        phases.append(entry)

    return {
        "phases": phases,
        "unlock_chain": [
            GlobalPhase.FOUNDATION.value,
            GlobalPhase.ROLE_SPECIALIZATION.value,
            GlobalPhase.ADVANCED.value,
            GlobalPhase.FRONTIER.value,
            "continuous_curriculum",
        ],
        "train_scripts": {
            "foundation": "oss/cli/intelligence_train.py",
            "role_specialization": "oss/cli/domain_research_train.py",
            "advanced": "native/windows/train.bat",
            "frontier": "continuous — kernel tick logs → shard promotion",
        },
    }


def progress_report(progress: TrainingProgress) -> dict[str, Any]:
    """Current unlock status for all roles."""
    return {
        "global_phase": progress.global_phase.value,
        "started_ts": progress.started_ts,
        "roles": {
            k: evaluate_role_unlock(AgentRole(k), v)
            for k, v in progress.roles.items()
        },
        "ready_for_global_advance": all(
            evaluate_role_unlock(AgentRole(k), v)["unlocked"]
            for k, v in progress.roles.items()
        ),
    }