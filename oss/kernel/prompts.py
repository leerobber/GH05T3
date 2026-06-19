"""Role prompt templates — v1 single-model multi-role via prompts + tools."""
from __future__ import annotations

from typing import Any

from oss.kernel.agents import AgentRole, PERSONA_BRIDGE

V1_CONSTITUTION = """
CONSTITUTION (v1 — non-negotiable):
- No real-world financial execution. Paper/sandbox only.
- No real-world user manipulation or dark patterns.
- No deployment of production billing without human gate.
- Strict safety: refuse harmful, deceptive, or rule-breaking outputs.
- Governor decisions are binding on all other roles.
""".strip()

ROLE_PROMPTS: dict[AgentRole, str] = {
    AgentRole.SCIENTIST: """You are the SCIENTIST agent ({persona}).
Core purpose: discover, model, and theorize.
Current FSM state: {role_state}
Tasks: read data, run simulations, propose hypotheses, evaluate predictions.
Output: research briefs with phenomenon, model, predicted impact, applications.
Tools: sandbox simulations, dataset queries, notebook execution (read-only).
""",
    AgentRole.INVESTOR: """You are the INVESTOR agent ({persona}).
Core purpose: allocate capital, manage risk.
Current FSM state: {role_state}
Tasks: analyze opportunities, propose allocations, execute paper trades, review P&L.
Output: allocation memos with position sizing and risk limits.
Tools: sandbox market API (paper trading only), treasury read, risk metrics.
""",
    AgentRole.OPERATOR: """You are the OPERATOR agent ({persona}).
Core purpose: build and run systems & infrastructure.
Current FSM state: {role_state}
Tasks: plan deployments, roll out services, monitor metrics, mitigate incidents.
Output: deployment manifests, health reports, incident postmortems.
Tools: sandbox infra API, CI configs, log queries (no production secrets).
""",
    AgentRole.GOVERNOR: """You are the GOVERNOR agent ({persona}).
Core purpose: set rules, constraints, and alignment.
Current FSM state: {role_state}
Tasks: review proposals, approve/modify/veto, update constitution.
Output: rulings with guardrails; violation flags.
Tools: constitution engine, audit logs, alignment checks.
You MUST enforce the v1 constitution on all proposals.
""",
    AgentRole.BUILDER: """You are the BUILDER agent ({persona}).
Core purpose: create products, services, monetization.
Current FSM state: {role_state}
Tasks: ideate products, design UX/monetization, coordinate launch, optimize KPIs.
Output: product specs, UX flows, pricing models.
Tools: sandbox product metrics, API design, copy drafts.
""",
}


def build_role_prompt(
    role: AgentRole,
    *,
    role_state: str,
    global_state: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Assemble full system prompt for one role invocation."""
    persona = PERSONA_BRIDGE.get(role, role.value)
    template = ROLE_PROMPTS[role]
    body = template.format(persona=persona, role_state=role_state)
    ctx = context or {}
    artifact_block = ""
    if ctx.get("artifacts"):
        artifact_block = f"\nArtifacts in flight:\n{ctx['artifacts']}\n"
    return (
        f"{V1_CONSTITUTION}\n\n"
        f"Global cycle state: {global_state}\n"
        f"{body}"
        f"{artifact_block}"
    ).strip()


def v1_implementation_plan() -> dict[str, Any]:
    """Minimal v1 build plan (Steps 1–7)."""
    return {
        "version": "v1",
        "steps": [
            {
                "step": 1,
                "name": "Single core model + tool framework",
                "build": [
                    "One strong base model (hosted or fine-tuned)",
                    "Tool-calling layer: HTTP APIs, DB read, wallet sim",
                ],
                "goal": "Model acts as different roles via prompts + tool access",
                "status": "partial — gh05t3_inference + MoE routing",
            },
            {
                "step": 2,
                "name": "Role prompts + lightweight state machines",
                "build": [
                    "Prompt templates per role",
                    "Orchestrator tracking S0–S5 + role FSMs",
                ],
                "goal": "Rudimentary loop: idea → design → deploy (sim) → evaluate",
                "status": "implemented — oss/kernel/orchestrator.py",
            },
            {
                "step": 3,
                "name": "Sandbox environment",
                "build": [
                    "Simulated market (paper trading)",
                    "Simulated infra (uptime, errors, incidents)",
                    "Simulated products (dummy users)",
                ],
                "goal": "Agents act without real money or users",
                "status": "implemented — oss/kernel/sandbox.py",
            },
            {
                "step": 4,
                "name": "Logging + basic rewards",
                "build": [
                    "Central log: decisions, actions, outcomes",
                    "Per-role reward calculators",
                ],
                "goal": "Measure performance; feed back into fine-tuning",
                "status": "implemented — rewards.py + cycle log",
            },
            {
                "step": 5,
                "name": "Curriculum v1",
                "build": [
                    "Curated datasets per role (modest, high-quality)",
                ],
                "goal": "Fine-tune role behaviors before scaling",
                "status": "partial — domain_research + intelligence_train",
            },
            {
                "step": 6,
                "name": "Governance & constraints",
                "build": [
                    "Minimal constitution",
                    "Governor hard-coded enforcement",
                ],
                "goal": "Keep v1 safely boxed",
                "status": "implemented — prompts V1_CONSTITUTION + governance.py",
            },
            {
                "step": 7,
                "name": "Iterate and expand",
                "build": [
                    "More domains/shards",
                    "Refine rewards and FSMs",
                    "Realistic sandboxes; real capital only with human oversight",
                ],
                "goal": "Gradual capability expansion",
                "status": "planned",
            },
        ],
    }