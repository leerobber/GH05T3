"""
Lab: Design and refine a trading strategy for a synthetic market.

Compares:
  - Old stack: static classes + backtest (simulated)
  - OSS stack: GenomicSubstrate + Investor agents + Omni-Mind + Omni-Economy
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from oss.substrate.genomic import CapabilityDescriptor, get_genomic_substrate
from oss.substrate.interaction_field import get_interaction_field
from oss.substrate.value_flow import get_value_flow
from oss.kernel.sandbox import MarketSandbox, reset_sandbox


# ── Old stack (files / classes / API mental model) ──────────────────────────

@dataclass
class OldStackResult:
    strategy: str
    sharpe: float
    max_drawdown: float
    params: dict[str, Any]
    iteration: str = "human_manual"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stack": "old_files_classes_api",
            "strategy": self.strategy,
            "sharpe": round(self.sharpe, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "params": self.params,
            "iteration": self.iteration,
        }


class TradingStrategy:
    """Old paradigm — fixed class with params."""

    def __init__(self, params: dict[str, Any]):
        self.params = params

    def generate_signals(self, prices: list[float]) -> list[int]:
        fast = int(self.params.get("fast", 10))
        slow = int(self.params.get("slow", 50))
        if len(prices) < slow + 1:
            return [0] * len(prices)
        signals = [0] * len(prices)
        for i in range(slow, len(prices)):
            ma_fast = sum(prices[i - fast:i]) / fast
            ma_slow = sum(prices[i - slow:i]) / slow
            signals[i] = 1 if ma_fast > ma_slow else -1 if ma_fast < ma_slow else 0
        return signals


def _backtest_old(prices: list[float], strategy: TradingStrategy) -> dict[str, float]:
    signals = strategy.generate_signals(prices)
    rets: list[float] = []
    position = 0
    for i in range(1, len(prices)):
        if signals[i] != position:
            position = signals[i]
        if position != 0:
            rets.append(position * (prices[i] - prices[i - 1]) / prices[i - 1])
    if not rets:
        return {"sharpe": 0.0, "max_drawdown": 0.0}
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / max(len(rets) - 1, 1)
    std = math.sqrt(var) if var > 0 else 1e-9
    sharpe = (mean / std) * math.sqrt(252)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in rets:
        equity *= 1 + r
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
    return {"sharpe": sharpe, "max_drawdown": max_dd}


def run_old_stack_lab(*, seed: int = 42) -> OldStackResult:
    """Simulate: human writes MA crossover, runs backtest once."""
    rng = random.Random(seed)
    market = MarketSandbox()
    prices = market.prices[:]
    for _ in range(30):
        prices.append(max(1.0, prices[-1] * (1 + rng.gauss(0, 0.01))))

    params = {"fast": 10, "slow": 50}
    strategy = TradingStrategy(params)
    metrics = _backtest_old(prices, strategy)
    return OldStackResult(
        strategy="moving_average_crossover",
        sharpe=metrics["sharpe"],
        max_drawdown=metrics["max_drawdown"],
        params=params,
    )


# ── OSS stack (genomes + swarm + economy) ───────────────────────────────────

def _strategy_from_traits(traits: dict[str, float], prices: list[float]) -> dict[str, Any]:
    """Investor agent proposes strategy from DNA traits (no fixed class)."""
    pattern = traits.get("pattern_detection", traits.get("finance", 0.5))
    risk = traits.get("risk_tolerance", traits.get("risk", 0.5))
    innovation = traits.get("innovation", traits.get("strategy", 0.5))

    if innovation > 0.65:
        name = "regime_switching_vol_target"
        fast, slow = 5, 30
    elif pattern > 0.6:
        name = "trend_following"
        fast, slow = 10, 40
    else:
        name = "conservative_mean_reversion"
        fast, slow = 15, 60

    fast = max(3, int(fast * (1.1 - risk)))
    slow = max(fast + 5, int(slow * (0.9 + risk * 0.2)))
    strategy = TradingStrategy({"fast": fast, "slow": slow})
    metrics = _backtest_old(prices, strategy)
    fitness = metrics["sharpe"] - metrics["max_drawdown"] * 2
    return {
        "name": name,
        "fast": fast,
        "slow": slow,
        "sharpe": metrics["sharpe"],
        "max_drawdown": metrics["max_drawdown"],
        "fitness_score": fitness,
        "description": f"{name} fast={fast} slow={slow} risk_tol={risk:.2f}",
    }


def run_oss_trading_lab(
    *,
    seed: int = 42,
    dry_run: bool = True,
    generations: int = 3,
) -> dict[str, Any]:
    """
    OSS lab: query strategists → propose → swarm eval → reward → evolve DNA.
    """
    rng = random.Random(seed)
    reset_sandbox()
    substrate = get_genomic_substrate()
    substrate.load_from_mind()

    # Seed investor genomes with trading traits if missing
    for gid in substrate.query_by_role("investor"):
        dna = substrate.get_genome(gid)
        if dna:
            for t in ("pattern_detection", "risk_tolerance", "market_intuition", "innovation", "creativity"):  # canonical + practical
                if t not in dna.traits:
                    dna.add_trait(t, 0.45 + rng.random() * 0.3)
            substrate.update_genome(gid, dna)

    # Also spawn dedicated strategists if pool thin
    cap = CapabilityDescriptor(domain="markets", skill="strategy_design", min_level=0.35)
    genome_ids = substrate.query_by_capability(cap)
    if len(genome_ids) < 2:
        from oss.substrate.species_registry import get_species_registry
        for _ in range(3):
            dna = get_species_registry().spawn("investor")
            for t, v in (
                ("pattern_detection", 0.5 + rng.random() * 0.3),
                ("risk_tolerance", 0.4 + rng.random() * 0.4),
                ("market_intuition", 0.5 + rng.random() * 0.2),
                ("innovation", 0.3 + rng.random() * 0.5),
            ):
                dna.add_trait(t, v)
            genome_ids.append(substrate.register_genome(dna))

    market = MarketSandbox()
    prices = list(market.prices)
    for _ in range(60):
        prices.append(max(1.0, prices[-1] * (1 + rng.gauss(0.0003, 0.012))))

    field = get_interaction_field()
    value = get_value_flow()
    cycle_log: list[dict[str, Any]] = []

    for gen in range(generations):
        proposals: list[dict[str, Any]] = []
        handles = []

        for gid in genome_ids[:5]:
            handle = substrate.spawn_agent(gid, "investor")
            handles.append(handle)
            dna = substrate.get_genome(gid)
            traits = {k: t.value for k, t in (dna.traits.items() if dna else {})}
            proposal = _strategy_from_traits(traits, prices)
            proposal["genome_id"] = gid
            proposal["agent_id"] = handle.agent_id

            intent = field.publish_intent(
                "allocation",
                handle.agent_id,
                {"type": "strategy_proposal", **proposal},
            )
            field.respond(
                intent.intent_id,
                agent=handle.agent_id,
                offer=proposal["description"],
                confidence=min(1.0, 0.4 + proposal["fitness_score"] * 0.2),
                risk=proposal["max_drawdown"],
            )
            proposals.append({**proposal, "intent_id": intent.intent_id})

        best = max(proposals, key=lambda p: p["fitness_score"])
        consensus = field.reach_consensus(best["intent_id"])

        # Omni-Mind consensus state (simulated)
        emergent_goal = {
            "description": "Find robust strategy for volatile regimes",
            "best_strategy": best["name"],
            "fitness": best["fitness_score"],
        }

        payouts: dict[str, Any] = {}
        for p in proposals:
            gid = p["genome_id"]
            score = max(0.0, min(1.0, 0.5 + p["fitness_score"] * 0.15))
            substrate.record_fitness(gid, score, {"task": "synthetic_trading", "gen": gen, "strategy": p["name"]})
            if not dry_run and p["genome_id"] == best["genome_id"]:
                payouts[p["agent_id"]] = value.earn(p["agent_id"], 100.0, "strategy_bounty")
                value.list_trait(gid, "pattern_detection", price_nc=50.0)
                value.maybe_soul_bond(p["agent_id"], score)
            mutated = substrate.mutate(gid, intensity=0.05 + (0.05 if p == best else 0.0))
            substrate.update_genome(gid, mutated)

        if gen == generations - 1 and len(genome_ids) >= 2:
            c1, c2 = substrate.crossover(genome_ids[0], genome_ids[1])
            genome_ids.extend([c1.genome_id, c2.genome_id])

        cycle_log.append({
            "generation": gen,
            "proposals": len(proposals),
            "best": best,
            "consensus": consensus,
            "emergent_goal": emergent_goal,
            "payouts": payouts,
        })

    return {
        "stack": "oss_genomic_substrate",
        "generations": generations,
        "genome_pool": len(genome_ids),
        "final_best": cycle_log[-1]["best"] if cycle_log else {},
        "cycles": cycle_log,
        "substrate_status": substrate.status(),
        "economy": value.snapshot(),
        "dry_run": dry_run,
    }


def trading_lab_comparison(*, seed: int = 42, dry_run: bool = True) -> dict[str, Any]:
    """Run both stacks side-by-side."""
    old = run_old_stack_lab(seed=seed)
    oss = run_oss_trading_lab(seed=seed, dry_run=dry_run)
    return {
        "problem": "Design and refine a trading strategy for a synthetic market",
        "old_stack": old.to_dict(),
        "oss_stack": oss,
        "contrast": {
            "old": "Static TradingStrategy class; human-tuned params; single backtest",
            "oss": "Living Investor genomes; swarm proposals; fitness-driven mutate/crossover; NC rewards",
        },
        "oss_wins_fitness": (
            oss.get("final_best", {}).get("fitness_score", 0)
            > old.sharpe - old.max_drawdown * 2
        ),
    }