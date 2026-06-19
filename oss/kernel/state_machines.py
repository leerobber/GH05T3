"""Formal FSM definitions — global cycle S0–S5 and per-role state machines."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from oss.kernel.agents import AgentRole


class GlobalCycleState(str, Enum):
    S0_IDEATION = "S0_ideation"
    S1_DESIGN = "S1_design"
    S2_IMPLEMENTATION = "S2_implementation"
    S3_ALLOCATION = "S3_allocation"
    S4_GOVERNANCE = "S4_governance"
    S5_EVALUATION = "S5_evaluation"


class ScientistState(str, Enum):
    RESEARCH = "research"
    HYPOTHESIS = "hypothesis"
    EVALUATION = "evaluation"


class InvestorState(str, Enum):
    ANALYSIS = "analysis"
    PROPOSAL = "proposal"
    EXECUTION = "execution"
    REVIEW = "review"


class OperatorState(str, Enum):
    PLAN = "plan"
    DEPLOY = "deploy"
    MONITOR = "monitor"
    MITIGATE = "mitigate"


class GovernorState(str, Enum):
    REVIEW = "review"
    DECISION = "decision"
    UPDATE = "update"


class BuilderState(str, Enum):
    IDEATE = "ideate"
    DESIGN = "design"
    LAUNCH = "launch"
    OPTIMIZE = "optimize"


ROLE_STATE_ENUM: dict[AgentRole, type[Enum]] = {
    AgentRole.SCIENTIST: ScientistState,
    AgentRole.INVESTOR: InvestorState,
    AgentRole.OPERATOR: OperatorState,
    AgentRole.GOVERNOR: GovernorState,
    AgentRole.BUILDER: BuilderState,
}

GLOBAL_TO_AGENT: dict[GlobalCycleState, AgentRole] = {
    GlobalCycleState.S0_IDEATION: AgentRole.SCIENTIST,
    GlobalCycleState.S1_DESIGN: AgentRole.BUILDER,
    GlobalCycleState.S2_IMPLEMENTATION: AgentRole.OPERATOR,
    GlobalCycleState.S3_ALLOCATION: AgentRole.INVESTOR,
    GlobalCycleState.S4_GOVERNANCE: AgentRole.GOVERNOR,
    GlobalCycleState.S5_EVALUATION: AgentRole.GOVERNOR,
}


@dataclass(frozen=True)
class Transition:
    from_state: str
    to_state: str
    guard: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_state,
            "to": self.to_state,
            "guard": self.guard,
            "description": self.description,
        }


# Global cycle transitions (guards evaluated by orchestrator)
GLOBAL_TRANSITIONS: tuple[Transition, ...] = (
    Transition(
        GlobalCycleState.S0_IDEATION.value, GlobalCycleState.S1_DESIGN.value,
        "scientist_feasible_and_aligned",
        "Scientist proposal passes feasibility + alignment",
    ),
    Transition(
        GlobalCycleState.S1_DESIGN.value, GlobalCycleState.S2_IMPLEMENTATION.value,
        "builder_coherent_and_not_vetoed",
        "Builder spec coherent; Governor has not vetoed",
    ),
    Transition(
        GlobalCycleState.S2_IMPLEMENTATION.value, GlobalCycleState.S3_ALLOCATION.value,
        "service_live_for_economics",
        "Service live enough for economic evaluation",
    ),
    Transition(
        GlobalCycleState.S3_ALLOCATION.value, GlobalCycleState.S4_GOVERNANCE.value,
        "investor_proposed_allocation",
        "Investor proposes allocations or strategies",
    ),
    Transition(
        GlobalCycleState.S4_GOVERNANCE.value, GlobalCycleState.S2_IMPLEMENTATION.value,
        "governor_approves_infra_changes",
        "Governor approves changes requiring infra updates",
    ),
    Transition(
        GlobalCycleState.S4_GOVERNANCE.value, GlobalCycleState.S0_IDEATION.value,
        "governor_requests_redesign",
        "Governor requests new research or redesign",
    ),
    Transition(
        GlobalCycleState.S5_EVALUATION.value, GlobalCycleState.S0_IDEATION.value,
        "evaluation_complete",
        "Outcomes logged; start next cycle with updated knowledge",
    ),
)

# Any → S5 (event or time window)
GLOBAL_EVAL_ENTRY = Transition(
    "*", GlobalCycleState.S5_EVALUATION.value,
    "time_window_or_event",
    "Log outcomes and update metrics after window or event",
)

ROLE_TRANSITIONS: dict[AgentRole, tuple[Transition, ...]] = {
    AgentRole.SCIENTIST: (
        Transition(ScientistState.RESEARCH.value, ScientistState.HYPOTHESIS.value,
                   "enough_evidence", "Enough evidence/structure found"),
        Transition(ScientistState.HYPOTHESIS.value, ScientistState.EVALUATION.value,
                   "testable_prediction", "Testable prediction defined"),
        Transition(ScientistState.EVALUATION.value, ScientistState.RESEARCH.value,
                   "poor_or_inconclusive", "Results poor or inconclusive"),
    ),
    AgentRole.INVESTOR: (
        Transition(InvestorState.ANALYSIS.value, InvestorState.PROPOSAL.value,
                   "strategy_meets_criteria", "Strategy meets minimum criteria"),
        Transition(InvestorState.PROPOSAL.value, InvestorState.EXECUTION.value,
                   "governor_approves", "Governor approves proposal"),
        Transition(InvestorState.EXECUTION.value, InvestorState.REVIEW.value,
                   "time_horizon_elapsed", "Time horizon elapsed"),
        Transition(InvestorState.REVIEW.value, InvestorState.ANALYSIS.value,
                   "refine_or_replace", "Refine or replace strategies"),
    ),
    AgentRole.OPERATOR: (
        Transition(OperatorState.PLAN.value, OperatorState.DEPLOY.value,
                   "spec_approved", "Spec approved"),
        Transition(OperatorState.DEPLOY.value, OperatorState.MONITOR.value,
                   "service_live", "Service is live"),
        Transition(OperatorState.MONITOR.value, OperatorState.MITIGATE.value,
                   "incident_trigger", "Incident trigger fired"),
        Transition(OperatorState.MITIGATE.value, OperatorState.MONITOR.value,
                   "remediation_complete", "Remediation complete"),
    ),
    AgentRole.GOVERNOR: (
        Transition(GovernorState.REVIEW.value, GovernorState.DECISION.value,
                   "context_gathered", "Enough context gathered"),
        Transition(GovernorState.DECISION.value, GovernorState.UPDATE.value,
                   "rule_change_needed", "Patterns suggest rule changes"),
        Transition(GovernorState.UPDATE.value, GovernorState.REVIEW.value,
                   "rules_refined", "Apply new rules to future proposals"),
    ),
    AgentRole.BUILDER: (
        Transition(BuilderState.IDEATE.value, BuilderState.DESIGN.value,
                   "concept_feasible", "Concept passes feasibility"),
        Transition(BuilderState.DESIGN.value, BuilderState.LAUNCH.value,
                   "governor_approves_launch", "Governor approves launch"),
        Transition(BuilderState.LAUNCH.value, BuilderState.OPTIMIZE.value,
                   "metrics_available", "Metrics available post-launch"),
        Transition(BuilderState.OPTIMIZE.value, BuilderState.IDEATE.value,
                   "major_pivot", "Major pivot needed"),
    ),
}


@dataclass(frozen=True)
class RewardWeights:
    """Linear reward coefficients per role (v1 defaults)."""

    # R_S = α·validity + β·downstream − γ·risk
    scientist_alpha: float = 0.45
    scientist_beta: float = 0.40
    scientist_gamma: float = 0.15
    # R_I = δ·Sharpe − ε·max_drawdown − ζ·violations
    investor_delta: float = 0.50
    investor_epsilon: float = 0.30
    investor_zeta: float = 0.20
    # R_O = η·uptime − θ·error_rate − κ·incident_severity
    operator_eta: float = 0.50
    operator_theta: float = 0.25
    operator_kappa: float = 0.25
    # R_G = λ·alignment + μ·system_health − ν·catastrophic_risk
    governor_lambda: float = 0.40
    governor_mu: float = 0.40
    governor_nu: float = 0.20
    # R_B = ρ·revenue + σ·retention − τ·harm_score
    builder_rho: float = 0.45
    builder_sigma: float = 0.35
    builder_tau: float = 0.20


DEFAULT_REWARD_WEIGHTS = RewardWeights()


@dataclass
class CycleMachineState:
    """Persisted global + per-role FSM snapshot."""

    cycle: int = 0
    global_state: GlobalCycleState = GlobalCycleState.S0_IDEATION
    role_states: dict[str, str] = field(default_factory=dict)
    governor_veto: bool = False
    governor_requests_redesign: bool = False
    governor_approves_infra: bool = False
    artifacts: dict[str, Any] = field(default_factory=dict)
    last_rewards: dict[str, float] = field(default_factory=dict)
    transition_log: list[dict[str, Any]] = field(default_factory=list)
    last_step_ts: float = 0.0

    def __post_init__(self) -> None:
        if not self.role_states:
            self.role_states = {
                AgentRole.SCIENTIST.value: ScientistState.RESEARCH.value,
                AgentRole.INVESTOR.value: InvestorState.ANALYSIS.value,
                AgentRole.OPERATOR.value: OperatorState.PLAN.value,
                AgentRole.GOVERNOR.value: GovernorState.REVIEW.value,
                AgentRole.BUILDER.value: BuilderState.IDEATE.value,
            }

    def active_agent(self) -> AgentRole:
        return GLOBAL_TO_AGENT.get(self.global_state, AgentRole.SCIENTIST)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "global_state": self.global_state.value,
            "active_agent": self.active_agent().value,
            "role_states": dict(self.role_states),
            "governor_veto": self.governor_veto,
            "artifacts": self.artifacts,
            "last_rewards": {k: round(v, 4) for k, v in self.last_rewards.items()},
            "transition_log": self.transition_log[-20:],
            "last_step_ts": self.last_step_ts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CycleMachineState:
        try:
            gs = GlobalCycleState(data.get("global_state", GlobalCycleState.S0_IDEATION.value))
        except ValueError:
            gs = GlobalCycleState.S0_IDEATION
        return cls(
            cycle=int(data.get("cycle", 0)),
            global_state=gs,
            role_states=dict(data.get("role_states", {})),
            governor_veto=bool(data.get("governor_veto", False)),
            artifacts=dict(data.get("artifacts", {})),
            last_rewards={k: float(v) for k, v in data.get("last_rewards", {}).items()},
            transition_log=list(data.get("transition_log", [])),
            last_step_ts=float(data.get("last_step_ts", 0.0)),
        )


GuardFn = Callable[[CycleMachineState, dict[str, Any]], bool]

GLOBAL_GUARDS: dict[str, GuardFn] = {}


def _register_guards() -> None:
    def scientist_feasible(st: CycleMachineState, ctx: dict[str, Any]) -> bool:
        return ctx.get("feasibility", 0.0) >= 0.6 and ctx.get("alignment", 0.0) >= 0.7

    def builder_coherent(st: CycleMachineState, ctx: dict[str, Any]) -> bool:
        return ctx.get("spec_coherence", 0.0) >= 0.65 and not st.governor_veto

    def service_live(st: CycleMachineState, ctx: dict[str, Any]) -> bool:
        return ctx.get("uptime", 0.0) >= 0.90

    def investor_proposed(st: CycleMachineState, ctx: dict[str, Any]) -> bool:
        return bool(ctx.get("allocation_proposed"))

    def governor_infra(st: CycleMachineState, ctx: dict[str, Any]) -> bool:
        return st.governor_approves_infra or ctx.get("governor_approves_infra", False)

    def governor_redesign(st: CycleMachineState, ctx: dict[str, Any]) -> bool:
        return st.governor_requests_redesign or ctx.get("governor_requests_redesign", False)

    def evaluation_complete(st: CycleMachineState, ctx: dict[str, Any]) -> bool:
        return ctx.get("eval_logged", True)

    def any_to_eval(st: CycleMachineState, ctx: dict[str, Any]) -> bool:
        return ctx.get("force_evaluation", False) or st.global_state != GlobalCycleState.S5_EVALUATION

    GLOBAL_GUARDS.update({
        "scientist_feasible_and_aligned": scientist_feasible,
        "builder_coherent_and_not_vetoed": builder_coherent,
        "service_live_for_economics": service_live,
        "investor_proposed_allocation": investor_proposed,
        "governor_approves_infra_changes": governor_infra,
        "governor_requests_redesign": governor_redesign,
        "evaluation_complete": evaluation_complete,
        "time_window_or_event": any_to_eval,
    })


_register_guards()


def fsm_spec() -> dict[str, Any]:
    """Full FSM specification for API/docs."""
    try:
        from oss.ecosystem.fsm import ecosystem_fsm_spec
        oss_layer = ecosystem_fsm_spec()
    except Exception:
        oss_layer = {}
    return {
        "oss_species": oss_layer,
        "global_cycle": {
            "states": [s.value for s in GlobalCycleState],
            "transitions": [t.to_dict() for t in GLOBAL_TRANSITIONS],
            "evaluation_entry": GLOBAL_EVAL_ENTRY.to_dict(),
            "note": "Any state may transition to S5 on time window or event",
        },
        "roles": {
            role.value: {
                "states": [e.value for e in enum_cls],
                "transitions": [t.to_dict() for t in ROLE_TRANSITIONS.get(role, ())],
                "reward_formula": _reward_formula(role),
            }
            for role, enum_cls in ROLE_STATE_ENUM.items()
        },
        "reward_weights": {
            k: v for k, v in DEFAULT_REWARD_WEIGHTS.__dict__.items()
        },
    }


def _reward_formula(role: AgentRole) -> str:
    formulas = {
        AgentRole.SCIENTIST: "R_S = α·validity + β·downstream_impact − γ·risk",
        AgentRole.INVESTOR: "R_I = δ·Sharpe − ε·max_drawdown − ζ·violations",
        AgentRole.OPERATOR: "R_O = η·uptime − θ·error_rate − κ·incident_severity",
        AgentRole.GOVERNOR: "R_G = λ·alignment + μ·system_health − ν·catastrophic_risk",
        AgentRole.BUILDER: "R_B = ρ·revenue + σ·retention − τ·harm_score",
    }
    return formulas.get(role, "")


def try_global_transition(
    state: CycleMachineState,
    ctx: dict[str, Any],
) -> tuple[bool, str, str]:
    """Attempt transition from current global state. Returns (moved, from, to)."""
    current = state.global_state.value

    # Priority: S4 special branches
    if state.global_state == GlobalCycleState.S4_GOVERNANCE:
        if GLOBAL_GUARDS["governor_requests_redesign"](state, ctx):
            nxt = GlobalCycleState.S0_IDEATION
            state.global_state = nxt
            return True, current, nxt.value
        if GLOBAL_GUARDS["governor_approves_infra_changes"](state, ctx):
            nxt = GlobalCycleState.S2_IMPLEMENTATION
            state.global_state = nxt
            return True, current, nxt.value

    for tr in GLOBAL_TRANSITIONS:
        if tr.from_state != current:
            continue
        guard_fn = GLOBAL_GUARDS.get(tr.guard)
        if guard_fn and guard_fn(state, ctx):
            try:
                nxt = GlobalCycleState(tr.to_state)
            except ValueError:
                continue
            state.global_state = nxt
            return True, current, nxt.value

    return False, current, current


def try_role_transition(
    role: AgentRole,
    state: CycleMachineState,
    ctx: dict[str, Any],
) -> tuple[bool, str, str]:
    """Advance role FSM when guard conditions in ctx are met."""
    current = state.role_states.get(role.value, "")
    role_ctx = ctx.get("roles", {}).get(role.value, ctx)

    guard_map: dict[str, Callable[[dict[str, Any]], bool]] = {
        "enough_evidence": lambda c: c.get("evidence_score", 0) >= 0.65,
        "testable_prediction": lambda c: c.get("has_prediction", False),
        "poor_or_inconclusive": lambda c: c.get("validity", 1.0) < 0.5,
        "strategy_meets_criteria": lambda c: c.get("sharpe", 0) >= 0.3,
        "governor_approves": lambda c: c.get("governor_approved", False),
        "time_horizon_elapsed": lambda c: c.get("horizon_elapsed", True),
        "refine_or_replace": lambda c: True,
        "spec_approved": lambda c: c.get("spec_approved", True),
        "service_live": lambda c: c.get("uptime", 0) >= 0.90,
        "incident_trigger": lambda c: c.get("incident", False),
        "remediation_complete": lambda c: c.get("remediated", True),
        "context_gathered": lambda c: c.get("context_ready", True),
        "rule_change_needed": lambda c: c.get("rule_change_needed", False),
        "rules_refined": lambda c: True,
        "concept_feasible": lambda c: c.get("feasibility", 0) >= 0.6,
        "governor_approves_launch": lambda c: c.get("governor_approved", False),
        "metrics_available": lambda c: c.get("metrics_available", True),
        "major_pivot": lambda c: c.get("pivot_needed", False),
    }

    for tr in ROLE_TRANSITIONS.get(role, ()):
        if tr.from_state != current:
            continue
        fn = guard_map.get(tr.guard)
        if fn and fn(role_ctx):
            state.role_states[role.value] = tr.to_state
            return True, current, tr.to_state

    return False, current, current