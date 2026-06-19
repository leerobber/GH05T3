"""
Lab: Design a new SaaS product for a synthetic user base.

Compares:
  - Old stack: ProductDesigner + ProductEvaluator classes + API mental model
  - OSS stack: GenomicSubstrate + Builder agents + Omni-Mind + Omni-Economy
               + domain_research_adapter when inference server is live
"""
from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oss.forge.lab_inference import complete_with_adapter, lab_inference_status
from oss.lab.metrics import (
    append_logs,
    compute_collective_metrics,
    load_logs,
    make_log_entry,
    trade_logs_from_transactions,
)
from oss.substrate.genomic import CapabilityDescriptor, get_genomic_substrate
from oss.substrate.interaction_field import get_interaction_field
from oss.substrate.value_flow import get_value_flow

_DATA_DIR = Path(__file__).resolve().parent / "data"


def load_lab_data() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    users = json.loads((_DATA_DIR / "users.json").read_text(encoding="utf-8"))
    market = json.loads((_DATA_DIR / "market.json").read_text(encoding="utf-8"))
    return users, market


def _segment_pain_index(users: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_seg: dict[str, list[str]] = {}
    for u in users:
        by_seg.setdefault(u["segment"], []).extend(u["pain_points"])
    return by_seg


def _top_segment(users: list[dict[str, Any]]) -> str:
    counts = Counter(u["segment"] for u in users)
    return counts.most_common(1)[0][0]


def _avg_budget(users: list[dict[str, Any]], segment: str) -> float:
    seg_users = [u for u in users if u["segment"] == segment]
    if not seg_users:
        return 79.0
    return sum(u["budget_monthly"] for u in seg_users) / len(seg_users)


def score_product(
    product: dict[str, Any],
    users: list[dict[str, Any]],
    market: dict[str, Any],
) -> float:
    """Shared evaluator — pain match, budget fit, competition gap, trend alignment."""
    segment = product.get("target_segment", "")
    seg_users = [u for u in users if u["segment"] == segment] or users
    pains = {p for u in seg_users for p in u["pain_points"]}
    blob = " ".join(
        [product.get("name", ""), product.get("value_prop", "")]
        + list(product.get("features", []))
    ).lower()

    pain_hits = sum(1 for p in pains if any(w in blob for w in p.split()))
    pain_score = pain_hits / max(len(pains), 1)

    price = product.get("pricing", {})
    raw_price = price.get("price", price.get("mid", 79))
    try:
        price_val = float(raw_price)
    except (TypeError, ValueError):
        price_val = 79.0
    budgets = [u["budget_monthly"] for u in seg_users]
    avg_budget = sum(budgets) / len(budgets)
    budget_fit = 1.0 - min(1.0, abs(price_val - avg_budget) / max(avg_budget, 1))

    competitors = market.get("competitors", [])
    comp_names = " ".join(c["name"].lower() for c in competitors)
    novelty = 0.15 if product.get("name", "").lower() in comp_names else 0.55

    trends = market.get("growth_trends", {})
    trend_blob = " ".join(product.get("features", [])).lower()
    trend_hits = sum(
        w for k, w in trends.items()
        if any(tok in trend_blob or tok in blob for tok in k.split("_"))
    )
    trend_score = min(1.0, trend_hits)

    adoption = 0.35 * pain_score + 0.25 * budget_fit + 0.2 * novelty + 0.2 * trend_score
    return round(min(1.0, max(0.0, adoption)), 4)


# ── Old stack ────────────────────────────────────────────────────────────────

@dataclass
class OldStackProductResult:
    product: dict[str, Any]
    score: float
    adoption_prediction: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "stack": "old_files_classes_api",
            "product": self.product,
            "score": self.score,
            "adoption_prediction": self.adoption_prediction,
            "iteration": "human_manual_single_shot",
        }


class ProductDesigner:
    """Old paradigm — one designer class, fixed heuristics."""

    def __init__(self, users: list[dict[str, Any]], market: dict[str, Any]):
        self.users = users
        self.market = market

    def propose_product(self) -> dict[str, Any]:
        segment = _top_segment(self.users)
        pains = _segment_pain_index(self.users).get(segment, [])
        top_pain = pains[0] if pains else "workflow friction"
        avg = _avg_budget(self.users, segment)
        return {
            "name": "SynthFlow",
            "target_segment": segment,
            "value_prop": f"Automated workflow mapping for {top_pain.replace('_', ' ')}",
            "features": ["workflow extraction", "dashboard", "alerts"],
            "pricing": {"tier": "subscription", "price": round(avg * 0.85, 2)},
        }


class ProductEvaluator:
    def __init__(self, users: list[dict[str, Any]], market: dict[str, Any]):
        self.users = users
        self.market = market

    def score_product(self, product: dict[str, Any]) -> float:
        return score_product(product, self.users, self.market)


def run_old_stack_lab(*, seed: int = 42) -> OldStackProductResult:
    users, market = load_lab_data()
    designer = ProductDesigner(users, market)
    evaluator = ProductEvaluator(users, market)
    product = designer.propose_product()
    s = evaluator.score_product(product)
    return OldStackProductResult(product=product, score=s, adoption_prediction=s)


# ── OSS stack ───────────────────────────────────────────────────────────────

def _product_from_traits(
    traits: dict[str, float],
    users: list[dict[str, Any]],
    market: dict[str, Any],
    *,
    rng: random.Random,
) -> dict[str, Any]:
    creativity = traits.get("creativity", traits.get("design", 0.5))
    empathy = traits.get("empathy", 0.5)
    # Normalized to extended UNIVERSAL_TRAITS (market_intuition, innovation now canonical)
    intuition = traits.get("market_intuition", traits.get("growth", 0.5))
    innovation = traits.get("innovation", traits.get("monetization", 0.5))

    segment = _top_segment(users)
    if empathy > 0.65:
        segment = max(_segment_pain_index(users), key=lambda s: len(_segment_pain_index(users)[s]))
    pains = _segment_pain_index(users).get(segment, ["fragmented tools"])
    pain = rng.choice(pains)

    if innovation > 0.7:
        name = "OmniFlow"
        pricing = {"tier": "usage-based", "price": "dynamic"}
        features = ["auto-mapping", "evolution tracking", "strategy suggestions"]
        value_prop = "Adaptive workflow AI that evolves with the business"
    elif creativity > 0.6:
        name = "PulseCanvas"
        pricing = {"tier": "subscription", "price": round(_avg_budget(users, segment) * 0.9, 2)}
        features = ["journey maps", "experiment board", "insight digests"]
        value_prop = f"Creative product discovery for {segment}"
    else:
        name = "SteadyOps"
        pricing = {"tier": "subscription", "price": round(_avg_budget(users, segment) * 0.75, 2)}
        features = ["checklists", "client portal", "billing sync"]
        value_prop = f"Reliable ops layer solving {pain}"

    if intuition > 0.65 and market.get("market_regime") == "volatile_demand":
        features.append("regime-aware pricing guardrails")

    return {
        "name": name,
        "target_segment": segment,
        "value_prop": value_prop,
        "features": features,
        "pricing": pricing,
        "inference_source": "traits_heuristic",
    }


def _maybe_adapter_product(
    traits: dict[str, float],
    users: list[dict[str, Any]],
    market: dict[str, Any],
    *,
    role: str,
    use_adapter: bool,
) -> dict[str, Any] | None:
    if not use_adapter:
        return None
    summary_users = json.dumps(users[:4], indent=0)[:1200]
    summary_market = json.dumps(market, indent=0)[:800]
    prompt = (
        f"Synthetic users:\n{summary_users}\n\n"
        f"Market context:\n{summary_market}\n\n"
        "Design one SaaS product for this user base."
    )
    result = complete_with_adapter(prompt=prompt, traits=traits, role=role, bucket="business")
    parsed = result.get("parsed")
    if parsed and parsed.get("name"):
        parsed["inference_source"] = result.get("source", "adapter")
        parsed["adapter_bucket"] = result.get("adapter_bucket", "business")
        return parsed
    return None


def run_oss_saas_lab(
    *,
    seed: int = 42,
    dry_run: bool = True,
    cycles: int = 10,
    use_adapter: bool = True,
) -> dict[str, Any]:
    rng = random.Random(seed)
    users, market = load_lab_data()
    substrate = get_genomic_substrate()
    substrate.load_from_mind()
    field = get_interaction_field()
    value = get_value_flow()

    cap = CapabilityDescriptor(domain="product", skill="creativity", min_level=0.35)
    genome_ids = substrate.query_by_capability(cap)
    if len(genome_ids) < 3:
        from oss.substrate.species_registry import get_species_registry
        for _ in range(5):
            dna = get_species_registry().spawn("builder")
            for t, v in (
                ("creativity", 0.5 + rng.random() * 0.35),
                ("empathy", 0.45 + rng.random() * 0.35),
                ("market_intuition", 0.5 + rng.random() * 0.3),
                ("innovation", 0.4 + rng.random() * 0.45),
                ("design", 0.5 + rng.random() * 0.25),
            ):
                dna.add_trait(t, v)
            genome_ids.append(substrate.register_genome(dna))

    cycle_log: list[dict[str, Any]] = []
    metrics_logs: list[dict[str, Any]] = []
    adapter_used = False

    for cycle in range(cycles):
        proposals: list[dict[str, Any]] = []
        pre_scores: dict[str, float] = {}

        for gid in genome_ids[:6]:
            handle = substrate.spawn_agent(gid, "builder")
            dna = substrate.get_genome(gid)
            traits = {k: round(t.value, 4) for k, t in (dna.traits.items() if dna else {})}

            product = _maybe_adapter_product(
                traits, users, market, role="builder", use_adapter=use_adapter,
            )
            if product:
                adapter_used = True
            else:
                product = _product_from_traits(traits, users, market, rng=rng)

            score = score_product(product, users, market)
            pre_scores[gid] = score

            intent = field.publish_intent(
                "product_design",
                handle.agent_id,
                {"type": "product_proposal", "cycle": cycle, **product},
            )
            field.respond(
                intent.intent_id,
                agent=handle.agent_id,
                offer=product.get("value_prop", ""),
                confidence=min(1.0, 0.35 + score * 0.6),
                cost_nc=2.0,
            )
            proposals.append({
                "genome_id": gid,
                "agent_id": handle.agent_id,
                "product": product,
                "score": score,
                "intent_id": intent.intent_id,
            })

        best = max(proposals, key=lambda p: p["score"])
        consensus = field.reach_consensus(best["intent_id"])
        rank = sorted((p["score"] for p in proposals), reverse=True)
        consensus_rank = rank.index(best["score"]) + 1
        consensus_accuracy = consensus_rank / max(len(rank), 1)

        emergent_goal = {
            "description": "Find robust SaaS for volatile demand regimes",
            "best_product": best["product"]["name"],
            "score": best["score"],
        }

        cycle_events: dict[str, list[str]] = {}
        for p in proposals:
            gid = p["genome_id"]
            agent_id = p["agent_id"]
            score = p["score"]
            substrate.record_fitness(
                gid, score,
                {"task": "saas_product_design", "cycle": cycle, "product": p["product"]["name"]},
            )
            events: list[str] = []
            pre = pre_scores.get(gid, score)
            mutated = substrate.mutate(gid, intensity=0.04 + (0.04 if p == best else 0.0))
            post_score = score_product(
                _product_from_traits(
                    {k: t.value for k, t in mutated.traits.items()},
                    users, market, rng=rng,
                ),
                users, market,
            )
            if abs(post_score - pre) > 0.02:
                events.append("mutation")
            substrate.update_genome(gid, mutated)

            nc = 0.0
            if not dry_run and p == best:
                nc = value.earn(agent_id, score * 100, "product_bounty")
                value.list_trait(gid, "creativity", price_nc=round(30 + score * 40, 2))
            elif dry_run and p == best:
                nc = score * 100

            parent_id = mutated.parent_id or ""
            if parent_id and cycle == 0:
                events.append("speciation")

            metrics_logs.append(make_log_entry(
                cycle=cycle,
                agent_id=agent_id,
                role="builder",
                traits={k: t.value for k, t in mutated.traits.items()},
                fitness=substrate.fitness_history(gid)[-1]["score"] if substrate.fitness_history(gid) else score,
                neurocoins=nc,
                proposal=p["product"],
                score=score,
                mutations={"delta_score": round(post_score - pre, 4)},
                lineage={"parent_id": parent_id, "genome_id": gid},
                events=events,
            ))
            cycle_events[agent_id] = events

        if cycle == cycles - 1 and len(genome_ids) >= 2:
            c1, c2 = substrate.crossover(genome_ids[0], genome_ids[1])
            genome_ids.extend([c1.genome_id, c2.genome_id])

        cycle_log.append({
            "cycle": cycle,
            "proposals": len(proposals),
            "best": best,
            "consensus": consensus,
            "consensus_accuracy": round(consensus_accuracy, 4),
            "emergent_goal": emergent_goal,
            "events": cycle_events,
        })

    append_logs(metrics_logs)
    collective = compute_collective_metrics(metrics_logs)

    return {
        "stack": "oss_genomic_substrate",
        "cycles": cycles,
        "genome_pool": len(genome_ids),
        "final_best": cycle_log[-1]["best"] if cycle_log else {},
        "cycles_detail": cycle_log,
        "substrate_status": substrate.status(),
        "economy": value.snapshot(),
        "inference": {
            **lab_inference_status(),
            "adapter_used_in_run": adapter_used,
            "use_adapter_requested": use_adapter,
        },
        "collective_metrics": collective,
        "dry_run": dry_run,
        "logs_written": len(metrics_logs),
    }


def saas_lab_comparison(
    *,
    seed: int = 42,
    dry_run: bool = True,
    cycles: int = 10,
    use_adapter: bool = True,
) -> dict[str, Any]:
    old = run_old_stack_lab(seed=seed)
    oss = run_oss_saas_lab(
        seed=seed, dry_run=dry_run, cycles=cycles, use_adapter=use_adapter,
    )
    old_score = old.score
    oss_score = oss.get("final_best", {}).get("score", 0)
    return {
        "problem": "Design a new SaaS product for a synthetic user base",
        "old_stack": old.to_dict(),
        "oss_stack": oss,
        "contrast": {
            "old": "Single ProductDesigner class; one shot; manual code edits to improve",
            "oss": "Builder genome swarm; domain_research_adapter + traits; fitness mutate/crossover",
        },
        "oss_wins_score": oss_score > old_score,
        "metrics_preview": oss.get("collective_metrics", {}),
    }


def lab_metrics_report() -> dict[str, Any]:
    logs = load_logs()
    df = None
    try:
        from oss.lab.metrics import logs_to_dataframe
        df = logs_to_dataframe(logs)
    except Exception:
        pass
    return {
        "log_entries": len(logs),
        "collective": compute_collective_metrics(logs),
        "agents": sorted({e["agent_id"] for e in logs}) if logs else [],
        "dataframe_rows": len(df) if df is not None else 0,
        "trade_logs": trade_logs_from_transactions(
            get_value_flow().transaction_history,
        ).to_dict(orient="records"),
    }