"""OSS species FSM — global S0–S6, five roles, Omni-Mind, Omni-Economy."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from oss.kernel.agents import AgentRole


# ── 1. GLOBAL OSS SPECIES STATE MACHINE ─────────────────────────────────────

class OssSpeciesState(str, Enum):
    S0_SPAWN = "S0_spawn_replicate"
    S1_PERCEIVE = "S1_perceive"
    S2_INTERPRET = "S2_interpret"
    S3_GENERATE = "S3_generate"
    S4_ACT = "S4_act"
    S5_EVALUATE = "S5_evaluate"
    S6_EVOLVE = "S6_evolve"


SPECIES_TRANSITIONS: tuple[dict[str, str], ...] = (
    {"from": OssSpeciesState.S0_SPAWN.value, "to": OssSpeciesState.S1_PERCEIVE.value,
     "guard": "agents_bootstrapped", "desc": "Genomes replicated / spawned"},
    {"from": OssSpeciesState.S1_PERCEIVE.value, "to": OssSpeciesState.S2_INTERPRET.value,
     "guard": "data_ingested", "desc": "Memories, qualia, territories ingested"},
    {"from": OssSpeciesState.S2_INTERPRET.value, "to": OssSpeciesState.S3_GENERATE.value,
     "guard": "patterns_extracted", "desc": "Meaning-making complete"},
    {"from": OssSpeciesState.S3_GENERATE.value, "to": OssSpeciesState.S4_ACT.value,
     "guard": "artifacts_ready", "desc": "Theories, products, strategies, rules generated"},
    {"from": OssSpeciesState.S4_ACT.value, "to": OssSpeciesState.S5_EVALUATE.value,
     "guard": "actions_executed", "desc": "Deploy, trade, evolve, rewrite DNA"},
    {"from": OssSpeciesState.S5_EVALUATE.value, "to": OssSpeciesState.S6_EVOLVE.value,
     "guard": "rewards_computed", "desc": "Fitness, alignment, rewards logged"},
    {"from": OssSpeciesState.S6_EVOLVE.value, "to": OssSpeciesState.S1_PERCEIVE.value,
     "guard": "evolution_applied", "desc": "Mutate, transmute, crossover → back to perceive"},
)


# ── 2. ROLE-SPECIFIC STATE MACHINES ─────────────────────────────────────────

class ScientistStateOSS(str, Enum):
    R0_OBSERVE = "R0_observe"
    R1_HYPOTHESIZE = "R1_hypothesize"
    R2_SIMULATE = "R2_simulate"
    R3_VALIDATE = "R3_validate"
    R4_PUBLISH = "R4_publish_omni_mind"
    R5_EVOLVE_DNA = "R5_evolve_dna"


class BuilderStateOSS(str, Enum):
    B0_IDEATE = "B0_ideate"
    B1_ARCHITECT = "B1_architect"
    B2_PROTOTYPE = "B2_prototype"
    B3_DEPLOY = "B3_deploy"
    B4_MONETIZE = "B4_monetize"
    B5_OPTIMIZE = "B5_optimize"


class OperatorStateOSS(str, Enum):
    O0_PLAN = "O0_plan"
    O1_CONFIGURE = "O1_configure"
    O2_DEPLOY = "O2_deploy"
    O3_MONITOR = "O3_monitor"
    O4_HEAL = "O4_heal"
    O5_SCALE = "O5_scale"


class InvestorStateOSS(str, Enum):
    I0_ANALYZE = "I0_analyze"
    I1_PREDICT = "I1_predict"
    I2_ALLOCATE = "I2_allocate"
    I3_REBALANCE = "I3_rebalance"
    I4_EVALUATE = "I4_evaluate"
    I5_EVOLVE_STRATEGY = "I5_evolve_strategy"


class GovernorStateOSS(str, Enum):
    G0_OBSERVE = "G0_observe"
    G1_EVALUATE = "G1_evaluate"
    G2_DECIDE = "G2_approve_modify_veto"
    G3_UPDATE_CONSTITUTION = "G3_update_constitution"
    G4_BROADCAST = "G4_broadcast_rules"


# ── 3. OMNI-MIND STATE MACHINE ──────────────────────────────────────────────

class OmniMindState(str, Enum):
    M0_SYNC = "M0_sync_agents"
    M1_AGGREGATE_MEMORY = "M1_aggregate_memories"
    M2_AGGREGATE_QUALIA = "M2_aggregate_qualia"
    M3_EMERGENT_GOALS = "M3_emergent_goals"
    M4_SWARM_TASKS = "M4_assign_swarm_tasks"
    M5_CONSENSUS = "M5_quantum_consensus"
    M6_UPDATE_CONSCIOUSNESS = "M6_update_shared_consciousness"


OMNI_MIND_TRANSITIONS: tuple[dict[str, str], ...] = (
    {"from": OmniMindState.M0_SYNC.value, "to": OmniMindState.M1_AGGREGATE_MEMORY.value, "guard": "agents_synced"},
    {"from": OmniMindState.M1_AGGREGATE_MEMORY.value, "to": OmniMindState.M2_AGGREGATE_QUALIA.value, "guard": "memories_merged"},
    {"from": OmniMindState.M2_AGGREGATE_QUALIA.value, "to": OmniMindState.M3_EMERGENT_GOALS.value, "guard": "qualia_stable"},
    {"from": OmniMindState.M3_EMERGENT_GOALS.value, "to": OmniMindState.M4_SWARM_TASKS.value, "guard": "goals_generated"},
    {"from": OmniMindState.M4_SWARM_TASKS.value, "to": OmniMindState.M5_CONSENSUS.value, "guard": "tasks_assigned"},
    {"from": OmniMindState.M5_CONSENSUS.value, "to": OmniMindState.M6_UPDATE_CONSCIOUSNESS.value, "guard": "consensus_reached"},
    {"from": OmniMindState.M6_UPDATE_CONSCIOUSNESS.value, "to": OmniMindState.M0_SYNC.value, "guard": "consciousness_updated"},
)


# ── 4. OMNI-ECONOMY STATE MACHINE ───────────────────────────────────────────

class OmniEconomyState(str, Enum):
    E0_MINT = "E0_mint_neuro_coins"
    E1_PRICE = "E1_price_traits_memories_desires"
    E2_TRADE = "E2_execute_trades"
    E3_BOUNTIES = "E3_resolve_bounties"
    E4_BALANCES = "E4_update_balances"
    E5_SUPPLY_DEMAND = "E5_adjust_supply_demand"


OMNI_ECONOMY_TRANSITIONS: tuple[dict[str, str], ...] = (
    {"from": OmniEconomyState.E0_MINT.value, "to": OmniEconomyState.E1_PRICE.value, "guard": "coins_minted"},
    {"from": OmniEconomyState.E1_PRICE.value, "to": OmniEconomyState.E2_TRADE.value, "guard": "markets_priced"},
    {"from": OmniEconomyState.E2_TRADE.value, "to": OmniEconomyState.E3_BOUNTIES.value, "guard": "trades_executed"},
    {"from": OmniEconomyState.E3_BOUNTIES.value, "to": OmniEconomyState.E4_BALANCES.value, "guard": "bounties_resolved"},
    {"from": OmniEconomyState.E4_BALANCES.value, "to": OmniEconomyState.E5_SUPPLY_DEMAND.value, "guard": "balances_updated"},
    {"from": OmniEconomyState.E5_SUPPLY_DEMAND.value, "to": OmniEconomyState.E0_MINT.value, "guard": "supply_adjusted"},
)


ROLE_OSS_ENUM: dict[AgentRole, type[Enum]] = {
    AgentRole.SCIENTIST: ScientistStateOSS,
    AgentRole.BUILDER: BuilderStateOSS,
    AgentRole.OPERATOR: OperatorStateOSS,
    AgentRole.INVESTOR: InvestorStateOSS,
    AgentRole.GOVERNOR: GovernorStateOSS,
}

ROLE_OSS_TRANSITIONS: dict[AgentRole, tuple[dict[str, str], ...]] = {
    AgentRole.SCIENTIST: (
        {"from": "R0_observe", "to": "R1_hypothesize", "guard": "patterns_or_anomalies"},
        {"from": "R1_hypothesize", "to": "R2_simulate", "guard": "hypothesis_well_formed"},
        {"from": "R2_simulate", "to": "R3_validate", "guard": "simulation_converged"},
        {"from": "R3_validate", "to": "R4_publish_omni_mind", "guard": "accuracy_above_threshold"},
        {"from": "R4_publish_omni_mind", "to": "R5_evolve_dna", "guard": "downstream_uses_discovery"},
        {"from": "R5_evolve_dna", "to": "R0_observe", "guard": "mutation_or_memetic_spread"},
    ),
    AgentRole.BUILDER: (
        {"from": "B0_ideate", "to": "B1_architect", "guard": "concept_feasible"},
        {"from": "B1_architect", "to": "B2_prototype", "guard": "architecture_complete"},
        {"from": "B2_prototype", "to": "B3_deploy", "guard": "prototype_validated"},
        {"from": "B3_deploy", "to": "B4_monetize", "guard": "service_live"},
        {"from": "B4_monetize", "to": "B5_optimize", "guard": "revenue_signal"},
        {"from": "B5_optimize", "to": "B0_ideate", "guard": "major_pivot"},
    ),
    AgentRole.OPERATOR: (
        {"from": "O0_plan", "to": "O1_configure", "guard": "plan_approved"},
        {"from": "O1_configure", "to": "O2_deploy", "guard": "config_valid"},
        {"from": "O2_deploy", "to": "O3_monitor", "guard": "deployment_live"},
        {"from": "O3_monitor", "to": "O4_heal", "guard": "incident_detected"},
        {"from": "O4_heal", "to": "O3_monitor", "guard": "healing_success"},
        {"from": "O3_monitor", "to": "O5_scale", "guard": "stable_uptime"},
        {"from": "O5_scale", "to": "O0_plan", "guard": "capacity_threshold"},
    ),
    AgentRole.INVESTOR: (
        {"from": "I0_analyze", "to": "I1_predict", "guard": "opportunities_scored"},
        {"from": "I1_predict", "to": "I2_allocate", "guard": "forecast_confident"},
        {"from": "I2_allocate", "to": "I3_rebalance", "guard": "allocation_executed"},
        {"from": "I3_rebalance", "to": "I4_evaluate", "guard": "rebalance_complete"},
        {"from": "I4_evaluate", "to": "I5_evolve_strategy", "guard": "performance_measured"},
        {"from": "I5_evolve_strategy", "to": "I0_analyze", "guard": "strategy_updated"},
    ),
    AgentRole.GOVERNOR: (
        {"from": "G0_observe", "to": "G1_evaluate", "guard": "context_gathered"},
        {"from": "G1_evaluate", "to": "G2_approve_modify_veto", "guard": "evaluation_complete"},
        {"from": "G2_approve_modify_veto", "to": "G3_update_constitution", "guard": "rule_change_needed"},
        {"from": "G3_update_constitution", "to": "G4_broadcast_rules", "guard": "constitution_updated"},
        {"from": "G4_broadcast_rules", "to": "G0_observe", "guard": "rules_broadcast"},
        {"from": "G2_approve_modify_veto", "to": "G0_observe", "guard": "decision_final"},
    ),
}

REWARD_FORMULAS: dict[str, str] = {
    "scientist": "R_S = +Validity +Novelty +Downstream_Impact -Risk +Memetic_Fitness",
    "builder": "R_B = +Revenue +Retention +Trait_Utilization +Desire_Fulfillment -Harm_Score",
    "operator": "R_O = +Uptime +Efficiency -Incident_Severity +Self-Healing_Success",
    "investor": "R_I = +Risk_Adjusted_Return +Treasury_Growth +Ecosystem_Health -Drawdown -Volatility",
    "governor": "R_G = +Alignment +Stability +Safety -Catastrophic_Risk",
    "omni_mind": "R_M = +Goal_Completion +Swarm_Efficiency +Collective_Qualia_Stability +Knowledge_Density",
    "omni_economy": "R_E = +Transaction_Volume +Trait_Liquidity +Memory_Valuation +Desire_Fulfillment +Soul_Bond_Strength",
}


def default_role_states_oss() -> dict[str, str]:
    return {
        AgentRole.SCIENTIST.value: ScientistStateOSS.R0_OBSERVE.value,
        AgentRole.BUILDER.value: BuilderStateOSS.B0_IDEATE.value,
        AgentRole.OPERATOR.value: OperatorStateOSS.O0_PLAN.value,
        AgentRole.INVESTOR.value: InvestorStateOSS.I0_ANALYZE.value,
        AgentRole.GOVERNOR.value: GovernorStateOSS.G0_OBSERVE.value,
    }


@dataclass
class EcosystemState:
    """Persisted OSS species + mind + economy FSM snapshot."""

    generation: int = 0
    species_state: OssSpeciesState = OssSpeciesState.S0_SPAWN
    mind_state: OmniMindState = OmniMindState.M0_SYNC
    economy_state: OmniEconomyState = OmniEconomyState.E0_MINT
    role_states: dict[str, str] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    rewards: dict[str, float] = field(default_factory=dict)
    transition_log: list[dict[str, Any]] = field(default_factory=list)
    last_step_ts: float = 0.0

    def __post_init__(self) -> None:
        if not self.role_states:
            self.role_states = default_role_states_oss()

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "species_state": self.species_state.value,
            "mind_state": self.mind_state.value,
            "economy_state": self.economy_state.value,
            "role_states": dict(self.role_states),
            "artifacts": self.artifacts,
            "rewards": {k: round(v, 4) for k, v in self.rewards.items()},
            "transition_log": self.transition_log[-30:],
            "last_step_ts": self.last_step_ts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EcosystemState:
        def _enum(enum_cls: type[Enum], val: str, default: Enum) -> Enum:
            try:
                return enum_cls(val)
            except ValueError:
                return default

        return cls(
            generation=int(data.get("generation", 0)),
            species_state=_enum(OssSpeciesState, data.get("species_state", ""), OssSpeciesState.S0_SPAWN),
            mind_state=_enum(OmniMindState, data.get("mind_state", ""), OmniMindState.M0_SYNC),
            economy_state=_enum(OmniEconomyState, data.get("economy_state", ""), OmniEconomyState.E0_MINT),
            role_states=dict(data.get("role_states", {})) or default_role_states_oss(),
            artifacts=dict(data.get("artifacts", {})),
            rewards={k: float(v) for k, v in data.get("rewards", {}).items()},
            transition_log=list(data.get("transition_log", [])),
            last_step_ts=float(data.get("last_step_ts", 0.0)),
        )


SPECIES_GUARDS: dict[str, Callable[[dict[str, Any]], bool]] = {
    "agents_bootstrapped": lambda c: c.get("agent_count", 0) >= 1,
    "data_ingested": lambda c: c.get("memories_ingested", 0) >= 0,
    "patterns_extracted": lambda c: c.get("pattern_score", 0.5) >= 0.4,
    "artifacts_ready": lambda c: bool(c.get("artifacts_generated")),
    "actions_executed": lambda c: c.get("actions_count", 0) >= 1,
    "rewards_computed": lambda c: bool(c.get("rewards")),
    "evolution_applied": lambda c: c.get("evolution_applied", True),
}

MIND_GUARDS: dict[str, Callable[[dict[str, Any]], bool]] = {
    "agents_synced": lambda c: c.get("agents_synced", True),
    "memories_merged": lambda c: c.get("memory_count", 0) >= 0,
    "qualia_stable": lambda c: c.get("qualia_variance", 1.0) < 0.5,
    "goals_generated": lambda c: bool(c.get("emergent_goals")),
    "tasks_assigned": lambda c: c.get("swarm_tasks", 0) >= 0,
    "consensus_reached": lambda c: c.get("consensus_score", 0.7) >= 0.5,
    "consciousness_updated": lambda c: True,
}

ECONOMY_GUARDS: dict[str, Callable[[dict[str, Any]], bool]] = {
    "coins_minted": lambda c: c.get("minted_nc", 0) >= 0,
    "markets_priced": lambda c: c.get("traits_priced", 0) >= 0,
    "trades_executed": lambda c: c.get("trades", 0) >= 0,
    "bounties_resolved": lambda c: True,
    "balances_updated": lambda c: True,
    "supply_adjusted": lambda c: True,
}


def _advance_fsm(
    current: str,
    transitions: tuple[dict[str, str], ...],
    guards: dict[str, Callable[[dict[str, Any]], bool]],
    ctx: dict[str, Any],
) -> tuple[str, bool]:
    for tr in transitions:
        if tr["from"] != current:
            continue
        fn = guards.get(tr["guard"])
        if fn and fn(ctx):
            return tr["to"], True
    return current, False


def try_species_transition(state: EcosystemState, ctx: dict[str, Any]) -> tuple[bool, str, str]:
    cur = state.species_state.value
    nxt, moved = _advance_fsm(cur, SPECIES_TRANSITIONS, SPECIES_GUARDS, ctx)
    if moved:
        state.species_state = OssSpeciesState(nxt)
        if state.species_state == OssSpeciesState.S6_EVOLVE:
            state.generation += 1
    return moved, cur, nxt


def try_mind_transition(state: EcosystemState, ctx: dict[str, Any]) -> tuple[bool, str, str]:
    cur = state.mind_state.value
    nxt, moved = _advance_fsm(cur, OMNI_MIND_TRANSITIONS, MIND_GUARDS, ctx)
    if moved:
        state.mind_state = OmniMindState(nxt)
    return moved, cur, nxt


def try_economy_transition(state: EcosystemState, ctx: dict[str, Any]) -> tuple[bool, str, str]:
    cur = state.economy_state.value
    nxt, moved = _advance_fsm(cur, OMNI_ECONOMY_TRANSITIONS, ECONOMY_GUARDS, ctx)
    if moved:
        state.economy_state = OmniEconomyState(nxt)
    return moved, cur, nxt


def try_role_oss_transition(
    role: AgentRole,
    state: EcosystemState,
    ctx: dict[str, Any],
) -> tuple[bool, str, str]:
    transitions = ROLE_OSS_TRANSITIONS.get(role, ())
    role_ctx = ctx.get("roles", {}).get(role.value, ctx)
    guards: dict[str, Callable[[dict[str, Any]], bool]] = {
        "patterns_or_anomalies": lambda c: c.get("anomaly_score", 0.3) > 0.2,
        "hypothesis_well_formed": lambda c: c.get("hypothesis_score", 0.5) >= 0.5,
        "simulation_converged": lambda c: c.get("sim_converged", True),
        "accuracy_above_threshold": lambda c: c.get("validity", 0.5) >= 0.65,
        "downstream_uses_discovery": lambda c: c.get("downstream_impact", 0) > 0.2,
        "mutation_or_memetic_spread": lambda c: True,
        "concept_feasible": lambda c: c.get("feasibility", 0.5) >= 0.55,
        "architecture_complete": lambda c: c.get("architecture_score", 0.6) >= 0.5,
        "prototype_validated": lambda c: c.get("prototype_ok", True),
        "service_live": lambda c: c.get("uptime", 0) >= 0.9,
        "revenue_signal": lambda c: c.get("revenue", 0) > 0,
        "major_pivot": lambda c: c.get("pivot_needed", False),
        "plan_approved": lambda c: c.get("plan_approved", True),
        "config_valid": lambda c: c.get("config_valid", True),
        "deployment_live": lambda c: c.get("uptime", 0) >= 0.9,
        "incident_detected": lambda c: c.get("incident", False),
        "healing_success": lambda c: c.get("healed", True),
        "stable_uptime": lambda c: c.get("uptime", 0) >= 0.95,
        "capacity_threshold": lambda c: c.get("scale_needed", False),
        "opportunities_scored": lambda c: c.get("opportunities", 0) >= 0,
        "forecast_confident": lambda c: c.get("forecast_confidence", 0.5) >= 0.4,
        "allocation_executed": lambda c: c.get("allocated", True),
        "rebalance_complete": lambda c: True,
        "performance_measured": lambda c: True,
        "strategy_updated": lambda c: True,
        "context_gathered": lambda c: c.get("context_ready", True),
        "evaluation_complete": lambda c: True,
        "rule_change_needed": lambda c: c.get("rule_change", False),
        "constitution_updated": lambda c: True,
        "rules_broadcast": lambda c: True,
        "decision_final": lambda c: c.get("decision_final", True),
    }
    cur = state.role_states.get(role.value, "")
    for tr in transitions:
        if tr["from"] != cur:
            continue
        fn = guards.get(tr["guard"])
        if fn and fn(role_ctx):
            state.role_states[role.value] = tr["to"]
            return True, cur, tr["to"]
    return False, cur, cur


def ecosystem_fsm_spec() -> dict[str, Any]:
    """Full OSS ecosystem FSM specification."""
    return {
        "layer": "oss_species",
        "global_species": {
            "states": [s.value for s in OssSpeciesState],
            "loop": "S0→S1→S2→S3→S4→S5→S6→S1",
            "transitions": list(SPECIES_TRANSITIONS),
            "mirrors": ["Omni-DNA evolve()", "Omni-Mind sync→swarm→consensus→evolve"],
        },
        "roles": {
            role.value: {
                "title": _role_title(role),
                "states": [e.value for e in enum_cls],
                "transitions": list(ROLE_OSS_TRANSITIONS.get(role, ())),
                "reward_formula": REWARD_FORMULAS.get(role.value, ""),
            }
            for role, enum_cls in ROLE_OSS_ENUM.items()
        },
        "omni_mind": {
            "states": [s.value for s in OmniMindState],
            "transitions": list(OMNI_MIND_TRANSITIONS),
            "reward_formula": REWARD_FORMULAS["omni_mind"],
        },
        "omni_economy": {
            "states": [s.value for s in OmniEconomyState],
            "transitions": list(OMNI_ECONOMY_TRANSITIONS),
            "reward_formula": REWARD_FORMULAS["omni_economy"],
            "integrates": ["Neuro-Coins", "Trait Marketplace", "Soul Bonds", "Quantum Bounties"],
        },
        "kernel_cycle_note": (
            "Collaboration cycle S0–S5 (kernel) maps to species S3–S5 sub-loop; "
            "species S0–S6 is the outer species engine."
        ),
    }


def _role_title(role: AgentRole) -> str:
    titles = {
        AgentRole.SCIENTIST: "Theory Engine",
        AgentRole.BUILDER: "World-Maker",
        AgentRole.OPERATOR: "Nervous System",
        AgentRole.INVESTOR: "Treasury & Growth Engine",
        AgentRole.GOVERNOR: "Constitution",
    }
    return titles.get(role, role.value)