from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

LOG = logging.getLogger("oss.adapter.swarm")

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


async def publish_task(task_id: str, problem: str, agent_ids: list[str]) -> None:
    """Publish swarm task to SwarmBus oss channel."""
    try:
        from swarm.bus import SwarmBus, SwarmMessage, MsgType
        bus = SwarmBus.instance()
        for agent_id in agent_ids:
            msg = SwarmMessage(
                channel="#oss/tasks",
                msg_type=MsgType.TASK,
                src="OmniMind",
                dst=agent_id,
                content=problem,
                metadata={"task_id": task_id},
            )
            await bus.publish(msg)
    except Exception as exc:
        LOG.warning("SwarmBus publish failed: %s", exc)


async def invoke_agent(registry_id: str, problem: str) -> dict:
    """Invoke specialist via agent_forge, else persona + ghost_llm cascade."""
    rid = registry_id.upper()
    persona_aliases = {rid}
    if rid == "GH05T3":
        persona_aliases.add("AVERY")

    for slug in (registry_id.lower(), registry_id, rid.lower()):
        try:
            from agent_forge import get_agent
            agent = get_agent(slug)
            if agent is not None:
                return await agent.invoke(
                    f"[Omni-DNA swarm]\n{problem}",
                    user_id="oss-swarm",
                    session_id="oss",
                )
        except Exception as exc:
            LOG.debug("forge miss %s: %s", slug, exc)

    try:
        from personas import get_persona
        persona = None
        for alias in persona_aliases:
            persona = get_persona(alias)
            if persona:
                break
        if persona:
            from ghost_llm import chat_once
            system = (
                f"You are {persona.name}, {persona.title} at Aethyro/GH05T3.\n"
                f"Style: {persona.voice}\n"
                f"Respond concisely to the swarm task."
            )
            text, provider = await chat_once(
                f"oss_swarm_{rid}_{int(time.time())}", system, problem
            )
            return {
                "agent_id": rid,
                "result": text,
                "provider": provider,
                "persona": persona.name,
            }
    except Exception as exc:
        LOG.warning("Persona invoke failed for %s: %s", rid, exc)

    return {
        "agent_id": rid,
        "error": "no agent or persona found",
        "result": "",
    }


async def invoke_agents_parallel(registry_ids: list[str], problem: str) -> list[dict]:
    tasks = [invoke_agent(rid, problem) for rid in registry_ids]
    return await asyncio.gather(*tasks)