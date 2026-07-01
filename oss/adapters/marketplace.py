"""Marketplace adapter — GHOST DECK delegate + Omni-Mind sub-jobs."""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

def _db_path() -> Path:
    return Path(os.environ.get(
        "MARKETPLACE_DB_PATH",
        str(_BACKEND / "memory" / "palace.db"),
    ))


def _conn():
    c = sqlite3.connect(_db_path(), timeout=10)
    c.row_factory = sqlite3.Row
    return c


async def post_job(
    task: str,
    tags: list[str] | None = None,
    reward: int = 20,
    posted_by: str = "ghostdeck",
    metadata: dict | None = None,
) -> str:
    import agent_marketplace as mkt
    mkt._DB_PATH = _db_path()
    from agent_marketplace import JobQueue
    return await JobQueue.instance().post(
        task=task,
        tags=tags,
        reward=reward,
        posted_by=posted_by,
        metadata=metadata,
    )


def list_jobs(status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    try:
        c = _conn()
        if status:
            rows = c.execute(
                "SELECT id, task, tags, reward, status, posted_by, claimed_by, "
                "created_at, completed_at, result FROM marketplace_jobs "
                "WHERE status=? ORDER BY created_at DESC LIMIT ?",
                (status.lower(), limit),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id, task, tags, reward, status, posted_by, claimed_by, "
                "created_at, completed_at, result FROM marketplace_jobs "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        c.close()
    except sqlite3.DatabaseError:
        return []
    out = []
    for row in rows:
        out.append({
            "id": row["id"],
            "task": row["task"],
            "tags": json.loads(row["tags"] or "[]"),
            "reward": row["reward"],
            "status": row["status"],
            "posted_by": row["posted_by"],
            "claimed_by": row["claimed_by"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
            "result": row["result"],
        })
    return out


def get_job(job_id: str) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute(
            "SELECT id, task, tags, reward, status, posted_by, claimed_by, "
            "created_at, completed_at, result, metadata FROM marketplace_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "task": row["task"],
        "tags": json.loads(row["tags"] or "[]"),
        "reward": row["reward"],
        "status": row["status"],
        "posted_by": row["posted_by"],
        "claimed_by": row["claimed_by"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
        "result": row["result"],
        "metadata": json.loads(row["metadata"] or "{}"),
    }


async def split_swarm_into_jobs(
    problem: str,
    agent_ids: list[str],
    reward_each: int = 15,
) -> list[str]:
    """Post sub-jobs when swarm task complexity exceeds threshold."""
    if len(problem) < 120 and len(agent_ids) <= 2:
        return []
    jobs = []
    for agent_id in agent_ids:
        job_id = await post_job(
            task=f"Sub-task for swarm: {problem[:200]}",
            tags=[agent_id.upper()],
            reward=reward_each,
            posted_by="omni_mind",
            metadata={"parent_problem": problem[:500]},
        )
        jobs.append(job_id)
    return jobs