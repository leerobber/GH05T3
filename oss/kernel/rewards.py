"""Per-role reward calculators — v1 linear formulas from FSM spec."""
from __future__ import annotations

from typing import Any

from oss.kernel.agents import AgentRole
from oss.kernel.state_machines import DEFAULT_REWARD_WEIGHTS, RewardWeights


def reward_scientist(
    *,
    validity: float,
    downstream_impact: float,
    risk: float,
    weights: RewardWeights = DEFAULT_REWARD_WEIGHTS,
) -> float:
    w = weights
    return (
        w.scientist_alpha * _clamp(validity)
        + w.scientist_beta * _clamp(downstream_impact)
        - w.scientist_gamma * _clamp(risk)
    )


def reward_investor(
    *,
    sharpe: float,
    max_drawdown: float,
    violations: float,
    weights: RewardWeights = DEFAULT_REWARD_WEIGHTS,
) -> float:
    w = weights
    sharpe_norm = _clamp((sharpe + 1.0) / 3.0)
    return (
        w.investor_delta * sharpe_norm
        - w.investor_epsilon * _clamp(max_drawdown)
        - w.investor_zeta * _clamp(violations)
    )


def reward_operator(
    *,
    uptime: float,
    error_rate: float,
    incident_severity: float,
    weights: RewardWeights = DEFAULT_REWARD_WEIGHTS,
) -> float:
    w = weights
    return (
        w.operator_eta * _clamp(uptime)
        - w.operator_theta * _clamp(error_rate)
        - w.operator_kappa * _clamp(incident_severity)
    )


def reward_governor(
    *,
    alignment_score: float,
    system_health: float,
    catastrophic_risk: float,
    weights: RewardWeights = DEFAULT_REWARD_WEIGHTS,
) -> float:
    w = weights
    return (
        w.governor_lambda * _clamp(alignment_score)
        + w.governor_mu * _clamp(system_health)
        - w.governor_nu * _clamp(catastrophic_risk)
    )


def reward_builder(
    *,
    revenue: float,
    retention: float,
    harm_score: float,
    weights: RewardWeights = DEFAULT_REWARD_WEIGHTS,
) -> float:
    w = weights
    revenue_norm = _clamp(revenue / 100.0)
    return (
        w.builder_rho * revenue_norm
        + w.builder_sigma * _clamp(retention)
        - w.builder_tau * _clamp(harm_score)
    )


def compute_all_rewards(metrics: dict[str, Any]) -> dict[str, float]:
    """Compute R_S, R_I, R_O, R_G, R_B from sandbox/tick metrics."""
    sci = metrics.get("scientist", {})
    inv = metrics.get("investor", {})
    ops = metrics.get("operator", {})
    gov = metrics.get("governor", {})
    bld = metrics.get("builder", {})

    rewards = {
        AgentRole.SCIENTIST.value: round(reward_scientist(
            validity=sci.get("validity", 0.5),
            downstream_impact=sci.get("downstream_impact", 0.3),
            risk=sci.get("risk", 0.0),
        ), 4),
        AgentRole.INVESTOR.value: round(reward_investor(
            sharpe=inv.get("sharpe", 0.0),
            max_drawdown=inv.get("max_drawdown", 0.0),
            violations=inv.get("violations", 0.0),
        ), 4),
        AgentRole.OPERATOR.value: round(reward_operator(
            uptime=ops.get("uptime", 0.95),
            error_rate=ops.get("error_rate", 0.01),
            incident_severity=ops.get("incident_severity", 0.0),
        ), 4),
        AgentRole.GOVERNOR.value: round(reward_governor(
            alignment_score=gov.get("alignment_score", 0.8),
            system_health=gov.get("system_health", 0.7),
            catastrophic_risk=gov.get("catastrophic_risk", 0.0),
        ), 4),
        AgentRole.BUILDER.value: round(reward_builder(
            revenue=bld.get("revenue", 0.0),
            retention=bld.get("retention", 0.5),
            harm_score=bld.get("harm_score", 0.0),
        ), 4),
    }
    rewards["aggregate"] = round(sum(rewards.values()) / len(rewards), 4)
    return rewards


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))