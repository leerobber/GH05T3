"""Memory facade — unified access to Palace and Cortex substrates."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

LOG = logging.getLogger("oss.adapter.memory")

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def memory_status() -> dict[str, Any]:
    """Surface availability and rough counts from both memory systems."""
    status: dict[str, Any] = {
        "palace": {"available": False, "rooms": 0},
        "cortex": {"available": False, "core_users": 0, "archival_events": 0},
    }
    try:
        from memory.memory_palace import MemoryPalace
        palace = MemoryPalace()
        rooms = getattr(palace, "rooms", {}) or {}
        status["palace"] = {
            "available": True,
            "rooms": len(rooms) if isinstance(rooms, dict) else 0,
        }
    except Exception as exc:
        LOG.debug("palace status: %s", exc)

    try:
        import memory_cortex as cortex
        with cortex._conn() as c:
            core = c.execute("SELECT COUNT(*) FROM core_memory").fetchone()
            arch = c.execute("SELECT COUNT(*) FROM archival_memory").fetchone()
        status["cortex"] = {
            "available": True,
            "core_users": int(core[0]) if core else 0,
            "archival_events": int(arch[0]) if arch else 0,
        }
    except Exception as exc:
        LOG.debug("cortex status: %s", exc)

    status["unified"] = status["palace"]["available"] or status["cortex"]["available"]
    return status


async def recall_unified(
    query: str,
    user_id: str = "default",
    top_k: int = 5,
    room: str | None = None,
    agent_id: str = "",
) -> dict[str, Any]:
    """Search Cortex recall first, then Palace semantic recall."""
    results: list[dict[str, Any]] = []
    sources: list[str] = []

    try:
        import memory_cortex as cortex
        ctx = await cortex.get_cortex().read(
            user_id=user_id, query=query, agent_id=agent_id, recall_k=top_k,
        )
        if ctx.strip():
            sources.append("cortex")
            results.append({"source": "cortex", "content": ctx.strip(), "score": None})
    except Exception as exc:
        LOG.debug("cortex recall: %s", exc)

    if len(results) < top_k:
        try:
            from memory.memory_palace import MemoryPalace
            palace = MemoryPalace()
            hits = await palace.recall(query, room=room, top_k=top_k - len(results))
            if hits:
                sources.append("palace")
                for h in hits:
                    entry = h if isinstance(h, dict) else {"content": str(h)}
                    entry["source"] = "palace"
                    results.append(entry)
        except Exception as exc:
            LOG.debug("palace recall: %s", exc)

    return {
        "query": query,
        "user_id": user_id,
        "count": len(results),
        "sources": sources,
        "results": results[:top_k],
    }


async def store_memory(
    user_id: str,
    content: str,
    agent_id: str = "oss",
    session_id: str = "",
    importance: float = 0.5,
) -> str | None:
    """Write through Cortex (archival + recall tiers by importance)."""
    try:
        import memory_cortex as cortex
        return await cortex.get_cortex().write(
            user_id=user_id,
            content=content,
            agent_id=agent_id,
            session_id=session_id,
            importance=importance,
        )
    except Exception as exc:
        LOG.warning("store_memory failed: %s", exc)
        return None