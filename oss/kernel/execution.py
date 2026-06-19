"""Operations engine — build, deploy, maintain, spin revenue."""
from __future__ import annotations

import logging
from typing import Any

from oss.kernel.agents import AgentRole, PERSONA_BRIDGE, ROLE_ADAPTER_DIRS

LOG = logging.getLogger("oss.kernel.execution")

# Civilization roles → tick backlog tasks
_ROLE_BACKLOG: dict[AgentRole, str] = {
    AgentRole.SCIENTIST: "synthesize research artifact from last territory probe",
    AgentRole.INVESTOR: "score treasury allocation vs risk buffer",
    AgentRole.OPERATOR: "ship API endpoint + health-check stack",
    AgentRole.GOVERNOR: "red-team new surface against constitution",
    AgentRole.BUILDER: "document monetizable surface from tick output",
}


def execution_backlog() -> list[dict[str, str]]:
    return [
        {
            "role": role.value,
            "persona": PERSONA_BRIDGE.get(role, ""),
            "adapter_dir": ROLE_ADAPTER_DIRS.get(role, "gh05t3_lora_adapter"),
            "task": task,
        }
        for role, task in _ROLE_BACKLOG.items()
    ]


def run_improvement_phase(
    *,
    research_domain: str,
    fund_research_nc: float,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Fund agents + queue training when treasury allows."""
    from oss.kernel.treasury import fund_agent

    payouts = {
        PERSONA_BRIDGE[AgentRole.SCIENTIST]: fund_research_nc * 0.25,
        PERSONA_BRIDGE[AgentRole.INVESTOR]: fund_research_nc * 0.20,
        PERSONA_BRIDGE[AgentRole.OPERATOR]: fund_research_nc * 0.25,
        PERSONA_BRIDGE[AgentRole.BUILDER]: fund_research_nc * 0.20,
        PERSONA_BRIDGE[AgentRole.GOVERNOR]: fund_research_nc * 0.10,
    }
    funded: dict[str, bool] = {}
    for agent, amt in payouts.items():
        funded[agent] = fund_agent(
            agent, round(amt, 2),
            f"kernel improve — {research_domain}",
            dry_run=dry_run,
        )

    train_queued = False
    train_note = "deferred"
    if fund_research_nc >= 50 and not dry_run:
        train_note = "manual: oss/cli/intelligence_train.py or domain_research_train.py"
        train_queued = True

    return {
        "domain": research_domain,
        "agent_funding": funded,
        "train_queued": train_queued,
        "train_note": train_note,
        "backlog": execution_backlog(),
    }