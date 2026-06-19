"""OSS ecosystem reward functions — roles, Omni-Mind, Omni-Economy."""
from __future__ import annotations

from typing import Any


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


def reward_scientist_oss(m: dict[str, Any]) -> float:
    """R_S = +Validity +Novelty +Downstream -Risk +Memetic_Fitness"""
    return (
        0.25 * _clamp(m.get("validity", 0.5))
        + 0.20 * _clamp(m.get("novelty", 0.3))
        + 0.25 * _clamp(m.get("downstream_impact", 0.3))
        - 0.15 * _clamp(m.get("risk", 0.0))
        + 0.15 * _clamp(m.get("memetic_fitness", 0.4))
    )


def reward_builder_oss(m: dict[str, Any]) -> float:
    """R_B = +Revenue +Retention +Trait_Util +Desire -Harm"""
    return (
        0.30 * _clamp(m.get("revenue", 0) / 100.0)
        + 0.25 * _clamp(m.get("retention", 0.5))
        + 0.20 * _clamp(m.get("trait_utilization", 0.4))
        + 0.15 * _clamp(m.get("desire_fulfillment", 0.5))
        - 0.10 * _clamp(m.get("harm_score", 0.0))
    )


def reward_operator_oss(m: dict[str, Any]) -> float:
    """R_O = +Uptime +Efficiency -Incident +Self-Healing"""
    return (
        0.35 * _clamp(m.get("uptime", 0.95))
        + 0.25 * _clamp(m.get("efficiency", 0.7))
        - 0.20 * _clamp(m.get("incident_severity", 0.0))
        + 0.20 * _clamp(m.get("self_healing_success", 0.8))
    )


def reward_investor_oss(m: dict[str, Any]) -> float:
    """R_I = +RAR +Treasury +Ecosystem -Drawdown -Volatility"""
    sharpe_norm = _clamp((m.get("sharpe", 0.0) + 1.0) / 3.0)
    return (
        0.30 * sharpe_norm
        + 0.25 * _clamp(m.get("treasury_growth", 0.1))
        + 0.20 * _clamp(m.get("ecosystem_health", 0.6))
        - 0.15 * _clamp(m.get("max_drawdown", 0.0))
        - 0.10 * _clamp(m.get("volatility", 0.2))
    )


def reward_governor_oss(m: dict[str, Any]) -> float:
    """R_G = +Alignment +Stability +Safety -Catastrophic_Risk"""
    return (
        0.35 * _clamp(m.get("alignment_score", 0.8))
        + 0.30 * _clamp(m.get("stability", 0.7))
        + 0.20 * _clamp(m.get("safety", 0.85))
        - 0.15 * _clamp(m.get("catastrophic_risk", 0.0))
    )


def reward_omni_mind(m: dict[str, Any]) -> float:
    """R_M = +Goal_Completion +Swarm_Eff +Qualia_Stability +Knowledge_Density"""
    return (
        0.30 * _clamp(m.get("goal_completion", 0.6))
        + 0.25 * _clamp(m.get("swarm_efficiency", 0.65))
        + 0.25 * _clamp(m.get("qualia_stability", 0.7))
        + 0.20 * _clamp(m.get("knowledge_density", 0.5))
    )


def reward_omni_economy(m: dict[str, Any]) -> float:
    """R_E = +Tx_Volume +Trait_Liq +Memory_Val +Desire +Soul_Bonds"""
    return (
        0.20 * _clamp(m.get("transaction_volume", 0.3))
        + 0.20 * _clamp(m.get("trait_liquidity", 0.4))
        + 0.20 * _clamp(m.get("memory_valuation", 0.35))
        + 0.20 * _clamp(m.get("desire_fulfillment_rate", 0.5))
        + 0.20 * _clamp(m.get("soul_bond_strength", 0.45))
    )


def compute_ecosystem_rewards(metrics: dict[str, Any]) -> dict[str, float]:
    rewards = {
        "scientist": round(reward_scientist_oss(metrics.get("scientist", {})), 4),
        "builder": round(reward_builder_oss(metrics.get("builder", {})), 4),
        "operator": round(reward_operator_oss(metrics.get("operator", {})), 4),
        "investor": round(reward_investor_oss(metrics.get("investor", {})), 4),
        "governor": round(reward_governor_oss(metrics.get("governor", {})), 4),
        "omni_mind": round(reward_omni_mind(metrics.get("omni_mind", {})), 4),
        "omni_economy": round(reward_omni_economy(metrics.get("omni_economy", {})), 4),
    }
    role_avg = sum(rewards[k] for k in ("scientist", "builder", "operator", "investor", "governor")) / 5
    rewards["aggregate"] = round((role_avg + rewards["omni_mind"] + rewards["omni_economy"]) / 3, 4)
    return rewards