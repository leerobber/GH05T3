"""Living loop — Omni-DNA → Omni-Mind → Omni-Economy as one organism."""
from __future__ import annotations

import re
import time
from typing import Any

from oss.architecture.diagram import LIVING_LOOP_STEPS
from oss.integration.embodiment import AgentEmbodiment
from oss.kernel.agents import AgentRole, PERSONA_BRIDGE
from oss.kernel.sandbox import get_sandbox
from oss.substrate.genomic import get_genomic_substrate
from oss.substrate.interaction_field import get_interaction_field
from oss.substrate.species_registry import get_species_registry
from oss.substrate.value_flow import get_value_flow

ROLE_ORDER: tuple[str, ...] = tuple(r.value for r in AgentRole)


def emerge_goals(shared_memory: dict[str, Any]) -> list[dict[str, Any]]:
    """Scan shared memory for patterns → emergent goals."""
    text = " ".join(str(v) for v in shared_memory.values()).lower()
    patterns = [
        (r"market|treasury|allocat", "design robust treasury protocol", 80.0),
        (r"quantum|physics|simulat", "advance simulation capability", 60.0),
        (r"incident|error|uptime", "improve platform resilience", 70.0),
        (r"product|revenue|monetiz", "optimize monetization surface", 55.0),
        (r"govern|align|safety", "strengthen constitutional guardrails", 45.0),
    ]
    goals: list[dict[str, Any]] = []
    for regex, desc, reward in patterns:
        if re.search(regex, text):
            goals.append({"description": desc, "reward_nc": reward, "source": "pattern_match"})
    if not goals:
        goals.append({"description": "explore next domain rotation", "reward_nc": 30.0, "source": "default"})
    return goals


def run_living_cycle(
    *,
    domain: str = "business",
    tick: int = 0,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    One full organism cycle:

    1. Role agents act (sandbox observations)
    2. Omni-DNA evolves
    3. Omni-Mind syncs + emergent goals
    4. Omni-Economy rewards + bounties
    5. Feedback into DNA meta + soul bonds
    6. Species metrics for next cycle
    """
    sandbox = get_sandbox()
    sandbox_out = sandbox.run_cycle(domain=domain, tick=tick)
    genomic = get_genomic_substrate()
    genomic.load_from_mind()
    field = get_interaction_field()
    value = get_value_flow()
    registry = get_species_registry()

    # ── Step 1: Role agents act (spawn from substrate, not static classes) ─
    role_actions: list[dict[str, Any]] = []
    intents: list[dict[str, Any]] = []
    spawned: dict[str, dict[str, Any]] = {}
    for role_name in ROLE_ORDER:
        schema = registry.get_role(role_name)
        if not schema:
            continue
        genome_ids = genomic.query_by_role(role_name)
        if not genome_ids:
            dna = registry.spawn(role_name)
            genome_ids = [genomic.register_genome(dna)]
        handle = genomic.spawn_agent(genome_ids[0], role_name)
        spawned[role_name] = handle.to_dict()
        dna = genomic.get_genome(handle.genome_id)
        if not dna:
            continue
        emb = AgentEmbodiment(dna=dna, role=schema)
        metrics = sandbox_out.get(role_name, {})
        emb.perceive({"kind": "sandbox_tick", "domain": domain, "metrics": metrics, "success": True})
        field_name = {
            "scientist": "research",
            "builder": "product_design",
            "operator": "deployment",
            "investor": "allocation",
            "governor": "governance",
        }.get(role_name, "swarm_solve")
        intent = field.publish_intent(
            field_name,
            emb.agent_id,
            {"domain": domain, "tick": tick, "metrics": metrics},
        )
        intents.append(intent.to_dict())
        act = emb.act({"action": field_name, "domain": domain, "summary": intent.intent_id})
        field.respond(
            intent.intent_id,
            agent=emb.agent_id,
            offer=act["artifact"],
            confidence=metrics.get("validity", metrics.get("uptime", 0.7)),
            cost_nc=1.0,
            risk=metrics.get("risk", metrics.get("incident_severity", 0.05)),
        )
        consensus = field.reach_consensus(intent.intent_id)
        role_actions.append({**act, "consensus": consensus})

    # ── Step 2: Omni-DNA evolve + fitness ledger ───────────────────────────
    evolution: dict[str, Any] = {}
    for role_name in ROLE_ORDER:
        schema = registry.get_role(role_name)
        if not schema:
            continue
        spawn = spawned.get(role_name)
        if not spawn:
            continue
        dna = genomic.get_genome(spawn["genome_id"])
        if not dna:
            continue
        emb = AgentEmbodiment(dna=dna, role=schema)
        metrics = sandbox_out.get(role_name, {})
        score = registry.reward_fn(role_name)(metrics)
        deltas = emb.evolve(score)
        genomic.update_genome(spawn["genome_id"], emb.dna)
        genomic.record_fitness(
            spawn["genome_id"],
            score,
            {"domain": domain, "tick": tick, "role": role_name, "source": "living_loop"},
        )
        evolution[role_name] = {
            "score": round(score, 4),
            "trait_deltas": deltas,
            "genome_id": spawn["genome_id"],
        }
        try:
            from oss.dna.store import get_store
            get_store().save(emb.dna)
        except Exception:
            pass

    # ── Step 3: Omni-Mind sync + goals ────────────────────────────────────
    mind_result: dict[str, Any] = {"synced": False, "goals": [], "swarm": None}
    try:
        from oss.mind.omni_mind import get_mind
        from oss.schemas.genome import SwarmTask

        mind = get_mind()
        if not mind.agents:
            mind.bootstrap()
        mind.sync_agents()
        snap = mind.collective.snapshot()
        goals = emerge_goals(mind.collective.shared_memory)
        mind_result["goals"] = goals
        mind_result["synced"] = True
        mind_result["collective"] = snap

        if goals and not dry_run:
            top = goals[0]
            bounty = value.create_bounty(top["description"], top["reward_nc"])
            mind_result["bounty_id"] = bounty.goal_id
        elif goals:
            mind_result["bounty_id"] = f"dry_{goals[0]['description'][:20]}"

        if tick % 3 == 0:
            task = SwarmTask(
                problem=f"[living_loop] {domain} tick {tick}: {goals[0]['description']}",
                required_traits=["coding", "self_reflection"],
                max_agents=3,
            )
            mind_result["swarm_task"] = task.to_dict()
    except Exception as exc:
        mind_result["error"] = str(exc)
        goals = emerge_goals({})
        mind_result["goals"] = goals

    # ── Step 4: Omni-Economy reward + trade ───────────────────────────────
    economy_result: dict[str, Any] = {"payouts": {}, "listings": [], "bonds": []}
    base_reward = 5.0 if dry_run else 10.0
    for role_name in ROLE_ORDER:
        spawn = spawned.get(role_name)
        if not spawn:
            continue
        persona = spawn["agent_id"]
        evo_score = evolution.get(role_name, {}).get("score", 0.5)
        task = {
            "reward": base_reward * (1 + evo_score),
            "reason": f"living_loop tick {tick} {role_name}",
            "tags": [persona],
            "research": role_name == "scientist",
            "coding": role_name == "operator",
            "collaborate": True,
            "swarm": tick % 3 == 0,
        }
        if not dry_run:
            payout = value.ddrs_reward(persona, task)
            economy_result["payouts"][persona] = payout
            if evo_score >= 0.6:
                bond = value.maybe_soul_bond(persona, evo_score)
                if bond:
                    economy_result["bonds"].append(bond.to_dict())
            if evo_score >= 0.55:
                dna = genomic.get_genome(spawn["genome_id"])
                listing = value.list_trait(
                    spawn["genome_id"],
                    list(dna.traits.keys())[0] if dna and dna.traits else "fitness",
                    price_nc=round(10 * evo_score, 2),
                )
                economy_result["listings"].append(listing.to_dict())
        else:
            economy_result["payouts"][persona] = {"mode": "dry_run", "would_reward": task["reward"]}

    if mind_result.get("bounty_id") and not dry_run:
        assignees = [PERSONA_BRIDGE[AgentRole(r)] for r in AgentRole][:3]
        bid = mind_result["bounty_id"]
        if bid in value.bounties:
            economy_result["bounty_resolution"] = value.resolve_bounty(bid, assignees)

    # ── Step 5: Feedback into DNA meta ────────────────────────────────────
    for role_name in ROLE_ORDER:
        spawn = spawned.get(role_name)
        if not spawn:
            continue
        dna = genomic.get_genome(spawn["genome_id"])
        if not dna:
            continue
        payout = economy_result["payouts"].get(spawn["agent_id"], {})
        dna.meta_dna["economic_fitness"] = evolution.get(role_name, {}).get("score", 0.5)
        dna.meta_dna["last_payout_mode"] = payout.get("mode", "none")
        if spawn["agent_id"] in value.soul_bonds:
            dna.meta_dna["soul_bond"] = value.soul_bonds[spawn["agent_id"]].strength
        genomic.update_genome(spawn["genome_id"], dna)

    # ── Step 6: Cycle summary ─────────────────────────────────────────────
    return {
        "tick": tick,
        "domain": domain,
        "dry_run": dry_run,
        "steps": [dict(s) for s in LIVING_LOOP_STEPS],
        "spawned_agents": list(spawned.values()),
        "role_actions": role_actions,
        "intents": intents,
        "evolution": evolution,
        "omni_mind": mind_result,
        "omni_economy": {
            **economy_result,
            "snapshot": value.snapshot(),
        },
        "sandbox": sandbox_out,
        "genomes_active": genomic.count(),
        "ts": time.time(),
    }


def living_loop_status() -> dict[str, Any]:
    from oss.architecture.diagram import architecture_spec
    from oss.architecture.modules import module_breakdown
    return {
        "architecture": architecture_spec(),
        "modules": module_breakdown(),
        "substrate": {
            "genomes": get_genomic_substrate().count() or "lazy",
            "open_intents": len(get_interaction_field().list_open()),
            "economy": get_value_flow().snapshot(),
        },
        "roles": get_species_registry().list_roles(),
    }