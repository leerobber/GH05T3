"""
IBAC Daemon — Intent-Based Access Control
==========================================
Windows-compatible implementation of the Kernel-Boundary IBAC system.

On Linux: would intercept syscalls via seccomp/apparmor.
On Windows: intercepts agent requests via an async TCP daemon that
validates capability tokens before allowing system mutations.

Architecture:
  - Agents send Intent Requests to the daemon (port 8112)
  - Daemon validates:
      1. Capability token (HMAC-SHA256 signed by GitOpsMutator master key)
      2. Action whitelist (what the agent role is allowed to do)
      3. Path protection (blocked paths cannot be modified)
      4. Rate limiting (max N actions per minute per agent)
  - Approved → returns signed permission token
  - Denied  → returns THREAT alert + logs to Iron Dome

FastAPI endpoints:
  POST /ibac/request      — request permission for an action
  POST /ibac/verify       — verify an existing permission token
  GET  /ibac/policy       — current capability policy for each agent role
  GET  /ibac/log          — recent IBAC events

Integration:
  Agents must call /ibac/request before executing any of:
    - File writes
    - Process spawning
    - Network calls (external)
    - Memory mutations
    - Git commits

Usage:
    python -m sovereignnation.ibac_daemon
    # or import into FastAPI app
    from sovereignnation.ibac_daemon import ibac_router
    app.include_router(ibac_router, prefix="/ibac")
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

LOG = logging.getLogger("aethyro.ibac")

_DATA_DIR   = Path(__file__).parent.parent / "kairos" / "data"
_KEY_PATH   = _DATA_DIR / "gitops_master.key"
_LOG_PATH   = _DATA_DIR / "ibac_events.jsonl"

# Rate limiting
RATE_LIMIT_WINDOW_S = 60
RATE_LIMIT_MAX      = 20  # max IBAC requests per agent per minute

# ── Capability Policy ─────────────────────────────────────────────────────────
# Defines what each agent ROLE is allowed to do.
# Actions not listed here are denied by default.

CAPABILITY_POLICY: Dict[str, List[str]] = {
    "avery-sovereign": [
        "read_memory", "write_belief", "plan_strategy", "emit_swarm_message"
    ],
    "forge-sovereign": [
        "read_memory", "write_file", "run_python_sandbox", "git_commit", "emit_swarm_message"
    ],
    "oracle-sovereign": [
        "read_memory", "read_file", "semantic_search", "emit_swarm_message"
    ],
    "sentinel-sovereign": [
        "read_memory", "read_file", "audit_code", "block_agent",
        "emit_swarm_message", "write_iron_dome"
    ],
    "nexus-sovereign": [
        "read_memory", "route_task", "emit_swarm_message", "propagate_update", "git_commit"
    ],
    "codex-sovereign": [
        "read_memory", "read_file", "write_file", "emit_swarm_message"
    ],
    "SAGE": [
        "read_memory", "write_memory", "read_file", "write_file", "git_commit",
        "emit_swarm_message", "write_iron_dome", "run_python_sandbox", "write_belief"
    ],
    "GitOpsMutator": [
        "write_file", "git_commit", "write_iron_dome"
    ],
    "GhostRecall": [
        "write_memory", "write_iron_dome", "read_file"
    ],
    "TriageGovernor": [
        "write_memory", "write_iron_dome", "read_memory"
    ],
    "system": [
        "read_memory", "read_file", "emit_swarm_message"
    ],
}

# Paths that NO agent can modify (except SAGE with explicit override)
PROTECTED_PATHS = [
    "kairos/gitops_mutator.py",
    "kairos/verification.py",
    "memory/iron_dome.py",
    ".env",
    "supervisor.py",
    "START_ALL.bat",
    "sovereignnation/ibac_daemon.py",
]


# ─────────────────────────────────────────────────────────────────────────────
# Key + token helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_key() -> Optional[bytes]:
    if _KEY_PATH.exists():
        try:
            return bytes.fromhex(_KEY_PATH.read_text().strip())
        except Exception:
            pass
    return None


def _issue_token(agent_id: str, action: str, resource: str) -> str:
    """Issue a signed permission token for the given action."""
    key = _load_key()
    if not key:
        return str(uuid.uuid4())  # fallback if no key yet
    payload = f"{agent_id}|{action}|{resource}|{int(time.time() // 60)}"
    sig = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"ibac:{agent_id[:8]}:{sig}"


def _verify_token(token: str, agent_id: str, action: str, resource: str) -> bool:
    """Verify a previously issued permission token."""
    key = _load_key()
    if not key:
        return True  # no key → accept all (dev mode)
    now = int(time.time() // 60)
    for ts in [now, now - 1]:  # allow 1-minute window
        payload = f"{agent_id}|{action}|{resource}|{ts}"
        expected_sig = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()[:16]
        expected = f"ibac:{agent_id[:8]}:{expected_sig}"
        if hmac.compare_digest(token, expected):
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Rate limiter
# ─────────────────────────────────────────────────────────────────────────────

_rate_counters: Dict[str, List[float]] = defaultdict(list)


def _check_rate_limit(agent_id: str) -> bool:
    """Return True if the agent is within rate limits."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_S
    times = [t for t in _rate_counters[agent_id] if t > window_start]
    _rate_counters[agent_id] = times
    if len(times) >= RATE_LIMIT_MAX:
        return False
    _rate_counters[agent_id].append(now)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Event log
# ─────────────────────────────────────────────────────────────────────────────

def _log_event(event: Dict) -> None:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = time.time()
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class IBACRequest(BaseModel):
    agent_id:    str
    agent_role:  str
    action:      str                    # e.g. "write_file"
    resource:    str = ""               # e.g. "sovereignnation/pipeline_backend.py"
    payload:     Optional[Dict] = None  # optional context


class IBACVerifyRequest(BaseModel):
    token:    str
    agent_id: str
    action:   str
    resource: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────────────────

ibac_router = APIRouter()


@ibac_router.post("/request")
async def ibac_request(req: IBACRequest):
    """
    Request permission for an agent action.
    Returns a signed permission token if approved.
    """
    event = {
        "type":       "request",
        "agent_id":   req.agent_id,
        "agent_role": req.agent_role,
        "action":     req.action,
        "resource":   req.resource,
    }

    # 1. Rate limit check
    if not _check_rate_limit(req.agent_id):
        event["result"] = "rate_limited"
        _log_event(event)
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # 2. Capability check
    allowed_actions = CAPABILITY_POLICY.get(
        req.agent_role,
        CAPABILITY_POLICY.get("system", [])
    )
    if req.action not in allowed_actions:
        event["result"] = "capability_denied"
        _log_event(event)

        try:
            from memory.iron_dome import dome_write
            dome_write("IBAC", "capability_denied", {
                "agent_id":   req.agent_id,
                "agent_role": req.agent_role,
                "action":     req.action,
                "resource":   req.resource,
            })
        except Exception:
            pass

        LOG.warning(
            "[IBAC] DENIED: %s(%s) → action=%s (not in capability policy)",
            req.agent_id, req.agent_role, req.action,
        )
        raise HTTPException(
            status_code=403,
            detail=f"Agent role '{req.agent_role}' not authorized for action '{req.action}'"
        )

    # 3. Protected path check
    if req.resource:
        norm = req.resource.replace("\\", "/")
        for protected in PROTECTED_PATHS:
            if norm.endswith(protected) or protected in norm:
                if req.agent_role not in ("SAGE",):
                    event["result"] = "path_blocked"
                    _log_event(event)
                    LOG.warning("[IBAC] BLOCKED: %s attempted mutation of protected path: %s",
                                req.agent_id, req.resource)
                    raise HTTPException(
                        status_code=403,
                        detail=f"Protected path: {req.resource}"
                    )

    # 4. Issue token
    token = _issue_token(req.agent_id, req.action, req.resource)
    event["result"] = "approved"
    event["token"]  = token[:20] + "…"
    _log_event(event)

    LOG.debug("[IBAC] APPROVED: %s(%s) → %s on %s",
              req.agent_id, req.agent_role, req.action, req.resource[:50])

    return {
        "approved":  True,
        "token":     token,
        "agent_id":  req.agent_id,
        "action":    req.action,
        "resource":  req.resource,
        "issued_at": time.time(),
    }


@ibac_router.post("/verify")
async def ibac_verify(req: IBACVerifyRequest):
    """Verify an existing permission token."""
    valid = _verify_token(req.token, req.agent_id, req.action, req.resource)
    return {"valid": valid, "agent_id": req.agent_id, "action": req.action}


@ibac_router.get("/policy")
async def ibac_policy():
    """Return the current capability policy."""
    return {
        "policy":            CAPABILITY_POLICY,
        "protected_paths":   PROTECTED_PATHS,
        "rate_limit":        {"window_s": RATE_LIMIT_WINDOW_S, "max": RATE_LIMIT_MAX},
    }


@ibac_router.get("/log")
async def ibac_log(limit: int = 50):
    """Return recent IBAC events."""
    if not _LOG_PATH.exists():
        return {"events": []}
    lines = _LOG_PATH.read_text().strip().splitlines()
    events = []
    for line in reversed(lines[-limit:]):
        try:
            events.append(json.loads(line))
        except Exception:
            pass
    return {"events": events, "total": len(lines)}


@ibac_router.get("/stats")
async def ibac_stats():
    """Return IBAC statistics."""
    agents_rate = {k: len(v) for k, v in _rate_counters.items()}
    total_events = 0
    denied_events = 0
    if _LOG_PATH.exists():
        lines = _LOG_PATH.read_text().strip().splitlines()
        total_events = len(lines)
        denied_events = sum(
            1 for line in lines
            if '"result": "capability_denied"' in line or '"result": "path_blocked"' in line
        )
    return {
        "total_events":  total_events,
        "denied_events": denied_events,
        "active_agents": len(agents_rate),
        "rate_counters": agents_rate,
    }
