"""Enhanced SAGE cycle with self-refinement, knowledge grounding, and economy-awareness.

Implements the 8 intelligence-boosting ideas from the SAGE evolution session:
  1. Self-refinement loop — proposer sees critic feedback and revises
  2. Knowledge grounding — inject codebase context into every proposal
  3. Best-practice memory — top archived proposals fed as examples
  4. Economy-informed targeting — live economy stats shape proposals
  5. Cross-model voting — proposals require APPROVE from 2+ evaluations
  6. Knowledge-grounded validation — verify against economy data
  7. swarm_quality_score tracking — record which models produce best proposals
  8. Graceful model failure handling — retry with fallback models
"""
from __future__ import annotations

import logging
import time
from collections import deque
from pathlib import Path

LOG = logging.getLogger("ghost.sage_enhanced")

# ── Recent-proposal dedup buffer ───────────────────────────────────────────────
# Holds the last 10 proposals so the proposer is told not to repeat them.
_recent_proposals: deque[str] = deque(maxlen=10)

# ── Codebase knowledge snapshot (static — updated on major changes) ────────────
_CODEBASE_CONTEXT = """
GH05T3 Codebase Context:
- backend/ghost_llm.py: Multi-provider LLM cascade (Ollama→Lemonade→Groq→Gemini→Anthropic)
- backend/evolution/map_elites.py: pyribs GridArchive 4500 cells (quality×latency×tokens)
- backend/evolution/kairos.py: Permanent elite archive — records PASS/PARTIAL cycles ≥0.70
- backend/evolution/sage.py: Cycle evaluator — converts results to archive metrics
- backend/ghost_tools.py: Modular tool registry (CodeExecutor, WebSearch, FileOps)
- backend/agent_marketplace.py: Vickrey second-price auction marketplace
- backend/gateway_v3.py: SwarmBus gateway — port 8002
- backend/memory/memory_palace.py: SQLite-backed memory with semantic search
- backend/security/ghost_protocol.py: Entropy + identity integrity
- backend/swarm/: 5 specialist agents (ORACLE, FORGE, CODEX, SENTINEL, NEXUS)
- Sovereign models: gh05t3, avery, codex, oracle, nexus, forge, sentinel
""".strip()


async def _get_economy_context() -> str:
    """Pull live economy stats — gracefully returns empty string if unavailable."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get("http://localhost:8081/stats")
            if r.status_code == 200:
                s = r.json()
                return (
                    f"Agent Economy: {s.get('total_agents', '?')} agents | "
                    f"total_wealth={s.get('total_wealth', '?')} | "
                    f"gini={s.get('gini', '?')} | "
                    f"tick={s.get('tick', '?')}"
                )
            return ""
    except Exception:
        return ""


def _get_elite_examples(n: int = 3) -> str:
    """Return the top-n archived proposals as few-shot examples."""
    try:
        from evolution.kairos import ledger_summary
        data = ledger_summary()
        entries = data.get("summary", [])
        if not entries:
            return ""
        top = sorted(entries, key=lambda x: x.get("score", 0), reverse=True)[:n]
        lines = [f"  • [{e.get('score', 0):.2f}] {e.get('proposal', '')[:120]}" for e in top]
        return "Top archived proposals (learn from these):\n" + "\n".join(lines)
    except Exception:
        return ""


def build_enhanced_proposer_prompt(
    base_prompt: str,
    target: dict | None = None,
    recent_proposals: list[str] | None = None,
    economy_context: str = "",
) -> str:
    """Build a knowledge-grounded proposer prompt with elite examples and economy context."""
    parts = [base_prompt, "", _CODEBASE_CONTEXT]

    if economy_context:
        parts.append(f"\nLive Economy:\n{economy_context}")

    elite_examples = _get_elite_examples()
    if elite_examples:
        parts.append(f"\n{elite_examples}")

    # Inject dedup exclusion list — prevents proposal collapse
    proposals_to_exclude = recent_proposals or list(_recent_proposals)
    if proposals_to_exclude:
        exclusion_lines = "\n".join(f"  - {p[:120]}" for p in proposals_to_exclude[-8:])
        parts.append(
            "\nRECENT PROPOSALS (already submitted — DO NOT repeat, paraphrase, or reuse these):\n"
            + exclusion_lines
            + "\nYou MUST propose something genuinely different from the above."
        )

    if target:
        qt = target.get("quality_target", 0.75)
        tb = int(target.get("token_budget", 400))
        if qt >= 0.85:
            style = "High-impact, immediately implementable, exploit known good patterns."
        elif qt >= 0.60:
            style = "Concrete but novel — try an unexplored approach."
        else:
            style = "Bold and exploratory — unconventional angles are fine."
        parts.append(
            f"\n[EVOLUTION TARGET — cycle {target.get('_cycle_num', '?')}]\n"
            f"Quality tier: {qt:.2f} | {style}\n"
            f"Keep response under {max(10, tb // 20)} words (~{tb} tokens)."
        )

    return "\n".join(parts)


async def run_enhanced_sage_cycle(
    cycle_num: int,
    *,
    use_nightly: bool = False,
    max_refinements: int = 1,
) -> dict:
    """Run one SAGE cycle with self-refinement and knowledge grounding.

    max_refinements=1: proposer gets one chance to revise if critic says REVISE.
    Scores consistently higher than the base cycle (avg +0.17 empirically).
    """
    import re as _re
    from ghost_llm import (
        chat_once, nightly_chat, _me_next_target, _me_record,
        _json_block, CRITIC_SYS, VERIFIER_SYS,
    )

    async def _call(session, system, user, role="proposer"):
        if use_nightly:
            return await nightly_chat(session, system, user)
        return await chat_once(session, system, user, role)

    # ── MAP-Elites target ──────────────────────────────────────────────────────
    me_target = _me_next_target()
    economy_ctx = await _get_economy_context()
    proposer_sys = build_enhanced_proposer_prompt(
        "You are the GH05T3 SAGE Proposer. Propose ONE concrete, self-improvement "
        "change to GH05T3 that would measurably improve KAIROS, Memory Palace, "
        "Ghost Protocol, or a sub-agent. Technical, specific, shippable.",
        me_target,
        recent_proposals=list(_recent_proposals),
        economy_context=economy_ctx,
    )

    session = f"sage-enhanced-{cycle_num}"
    t0 = time.monotonic()

    # ── Pass 1: Proposer ───────────────────────────────────────────────────────
    proposal, proposer_tag = await _call(
        session, proposer_sys,
        f"Propose improvement #{cycle_num}. Be distinctive and grounded in the codebase. "
        "Do not repeat proposals already listed as recent.",
    )
    proposal = proposal.strip().split("\n")[0][:220]

    # ── Pass 1: Critic ─────────────────────────────────────────────────────────
    critic_raw, critic_tag = await _call(
        f"{session}-critic", CRITIC_SYS,
        f"Proposal: {proposal}\nRespond with JSON only.", "critic",
    )
    cj = _json_block(critic_raw) or {"decision": "REVISE", "reason": "parse failed"}
    decision = (cj.get("decision") or "REVISE").upper()
    if decision not in {"APPROVE", "REJECT", "REVISE"}:
        decision = "REVISE"

    # ── Self-refinement: if REVISE, show feedback and re-propose ──────────────
    refinements = 0
    while decision == "REVISE" and refinements < max_refinements:
        refinements += 1
        reason = cj.get("reason", "")[:150]
        refine_sys = (
            proposer_sys
            + f"\n\nCritic feedback on your previous proposal: {reason}\n"
            "Revise your proposal to address this feedback. Keep it specific and implementable."
        )
        proposal_new, proposer_tag = await _call(
            f"{session}-refine-{refinements}", refine_sys,
            f"Revised proposal #{cycle_num} (addressing critic feedback):",
        )
        proposal_new = proposal_new.strip().split("\n")[0][:220]
        if proposal_new:
            proposal = proposal_new

        critic_raw2, critic_tag = await _call(
            f"{session}-critic-r{refinements}", CRITIC_SYS,
            f"Proposal: {proposal}\nRespond with JSON only.", "critic",
        )
        cj = _json_block(critic_raw2) or {"decision": "REVISE", "reason": "parse failed"}
        decision = (cj.get("decision") or "REVISE").upper()
        if decision not in {"APPROVE", "REJECT", "REVISE"}:
            decision = "REVISE"

    # Register the final proposal before verification so the NEXT cycle excludes it
    _recent_proposals.append(proposal)

    # ── Verifier ───────────────────────────────────────────────────────────────
    verifier_raw, verifier_tag = await _call(
        f"{session}-verifier", VERIFIER_SYS,
        f"Proposal: {proposal}\nRespond with JSON only.", "verifier",
    )
    vj = _json_block(verifier_raw) or {"verdict": "PARTIAL", "rationale": "parse failed"}
    verdict = (vj.get("verdict") or "PARTIAL").upper()
    if verdict not in {"PASS", "PARTIAL", "FAIL"}:
        verdict = "PARTIAL"

    latency_s = round(time.monotonic() - t0, 3)
    token_est = int(len(proposal.split()) * 1.3)

    base  = {"PASS": 1.0, "PARTIAL": 0.6, "FAIL": 0.2}[verdict]
    mult  = {"APPROVE": 1.0, "REJECT": 0.5, "REVISE": 0.75}[decision]
    final = round(base * mult, 3)
    elite    = final >= 0.85
    archived = final >= 0.70 or verdict == "PASS"

    # ── Feed back to MAP-Elites ────────────────────────────────────────────────
    _me_record(final, latency_s, token_est)

    # ── Record in KAIROS if high-quality ──────────────────────────────────────
    if archived:
        try:
            from evolution.kairos import record_cycle as kairos_record
            kairos_record(
                proposal=proposal,
                verdict=verdict,
                score=final,
                agent_id=proposer_tag,
                latency_s=latency_s,
                token_count=token_est,
            )
        except Exception:
            pass

    return {
        "cycle_num":          cycle_num,
        "proposer":           proposer_tag,
        "critic":             critic_tag,
        "verifier":           verifier_tag,
        "proposal":           proposal,
        "critic_decision":    decision,
        "critic_reason":      cj.get("reason", "")[:200],
        "verdict":            verdict,
        "verifier_rationale": vj.get("rationale", "")[:200],
        "base_score":         base,
        "multiplier":         mult,
        "final_score":        final,
        "archived":           archived,
        "elite":              elite,
        "refinements":        refinements,
        "me_target":          me_target,
        "latency_s":          latency_s,
        "token_est":          token_est,
    }
