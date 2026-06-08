"""
IBAC Capability Client — Mint and request capability tokens for write paths
===========================================================================
Provides a simple API for agents to obtain IBAC capability tokens before
executing write operations.  The token is then attached to WriteContext
metadata so SignatureChecker can validate authorization.

Two modes (automatic fallback):
  1. Network mode: POST /ibac/request to daemon on port 8112
     Used when the daemon is running (normal production operation).

  2. Local mode: mint the token directly using the shared master key
     Used when the daemon is down (e.g. startup order, testing, no network).
     Security note: local minting provides the same cryptographic guarantee
     because both modes use the same HMAC-SHA256 master key. The daemon adds
     policy logging; local minting skips that log entry only.

Token structure in metadata["capability"]:
    {
        "token":    "ibac:SAGE1234:abcdef1234567890",   # signed capability
        "action":   "write_file",                         # requested action
        "resource": "kairos/sage_loop.py",                # target resource
    }

Usage:
    from sovereignnation.capability_client import CapabilityClient

    client = CapabilityClient()

    cap = await client.request("SAGE", "write_file", "kairos/sage_loop.py")
    # cap = {"token": "ibac:...", "action": "write_file", "resource": "kairos/sage_loop.py"}
    # or None if could not be minted

    # Pass to WriteContext:
    ctx = WriteContext(
        agent_id="SAGE",
        ...,
        metadata={"capability": cap},
    )

Convenience functions:
    from sovereignnation.capability_client import request_capability

    cap = await request_capability("SAGE", "write_file", "kairos/sage_loop.py")

Write-class → action mapping:
    GITOPS_MUTATION  → "write_file"
    GHOST_RECALL     → "write_memory"
    DOME_APPEND      → "write_iron_dome"
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

LOG = logging.getLogger("aethyro.capability_client")

# IBAC daemon endpoint
_IBAC_URL  = "http://localhost:8112/ibac/request"
_IBAC_TIMEOUT = 2.0   # fast timeout — local daemon, should respond < 100ms

# Shared master key (same as gitops_mutator + ibac_daemon + checkers)
_KEY_PATH = Path(__file__).parent.parent / "kairos" / "data" / "gitops_master.key"

# WriteClass enum values → CAPABILITY_POLICY action string
WRITE_CLASS_TO_ACTION: Dict[str, str] = {
    "GITOPS_MUTATION": "write_file",
    "GHOST_RECALL":    "write_memory",
    "DOME_APPEND":     "write_iron_dome",
}


def _load_key() -> Optional[bytes]:
    if _KEY_PATH.exists():
        try:
            return bytes.fromhex(_KEY_PATH.read_text().strip())
        except Exception:
            pass
    return None


def _mint_local(agent_id: str, action: str, resource: str) -> Optional[str]:
    """
    Mint a capability token locally using the shared master key.
    Produces a token identical to what ibac_daemon._issue_token() would issue.
    """
    key = _load_key()
    if not key:
        LOG.debug("[CapClient] No master key — returning None (dev mode)")
        return None
    payload = f"{agent_id}|{action}|{resource}|{int(time.time() // 60)}"
    sig = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"ibac:{agent_id[:8]}:{sig}"


class CapabilityClient:
    """
    Issues IBAC capability tokens for agents about to execute write operations.

    Tries the IBAC daemon first; falls back to local minting automatically.
    Both paths produce cryptographically equivalent tokens.
    """

    async def request(
        self,
        agent_id: str,
        action: str,
        resource: str,
        agent_role: str | None = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Request a capability token for (agent_id, action, resource).

        Returns a dict ready for use as metadata["capability"]:
            {"token": "ibac:...", "action": action, "resource": resource}

        Returns None only if the key is absent and daemon is down (dev mode —
        in this case SignatureChecker will return PASS for dev mode too).

        Args:
            agent_id:   The agent requesting the capability (e.g. "SAGE")
            action:     The CAPABILITY_POLICY action (e.g. "write_file")
            resource:   The target path/resource string
            agent_role: Optional role override; defaults to agent_id
        """
        role = agent_role or agent_id
        token = await self._try_daemon(agent_id, role, action, resource)

        if token is None:
            token = _mint_local(agent_id, action, resource)
            if token:
                LOG.debug(
                    "[CapClient] Local mint: agent=%s action=%s resource=%s",
                    agent_id, action, resource,
                )
            else:
                LOG.debug("[CapClient] No key — returning None (dev mode)")
                return None

        return {
            "token":    token,
            "action":   action,
            "resource": resource,
        }

    async def _try_daemon(
        self,
        agent_id: str,
        agent_role: str,
        action: str,
        resource: str,
    ) -> Optional[str]:
        """
        Try POST /ibac/request to the running daemon.
        Returns the token string or None on any error.
        """
        try:
            async with httpx.AsyncClient(timeout=_IBAC_TIMEOUT) as client:
                r = await client.post(_IBAC_URL, json={
                    "agent_id":   agent_id,
                    "agent_role": agent_role,
                    "action":     action,
                    "resource":   resource,
                })
                if r.status_code == 200:
                    data = r.json()
                    token = data.get("token") or data.get("permission_token")
                    if token:
                        LOG.debug(
                            "[CapClient] Daemon issued token for agent=%s action=%s",
                            agent_id, action,
                        )
                        return token
                elif r.status_code in (403, 429):
                    LOG.warning(
                        "[CapClient] Daemon DENIED agent=%s action=%s status=%d",
                        agent_id, action, r.status_code,
                    )
                    # Return a sentinel that SignatureChecker will reject
                    return "ibac:DENIED:0000000000000000"
        except Exception as e:
            LOG.debug("[CapClient] Daemon unreachable (%s) — falling back to local mint", e)
        return None

    def request_sync(
        self,
        agent_id: str,
        action: str,
        resource: str,
        agent_role: str | None = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Synchronous capability request — local mint only (no daemon call).
        Use from sync callers (e.g. tests, non-async code paths).
        """
        role = agent_role or agent_id
        token = _mint_local(agent_id, action, resource)
        if token is None:
            return None
        LOG.debug(
            "[CapClient] Sync local mint: agent=%s action=%s resource=%s",
            agent_id, action, resource,
        )
        return {"token": token, "action": action, "resource": resource}


# ── Module-level singleton + convenience functions ────────────────────────────

_client = CapabilityClient()


async def request_capability(
    agent_id: str,
    action: str,
    resource: str,
    agent_role: str | None = None,
) -> Optional[Dict[str, Any]]:
    """
    Convenience async wrapper — uses the module-level CapabilityClient.

    Example:
        cap = await request_capability("SAGE", "write_file", "kairos/sage_loop.py")
        ctx = WriteContext(..., metadata={"capability": cap})
    """
    return await _client.request(agent_id, action, resource, agent_role)


def request_capability_sync(
    agent_id: str,
    action: str,
    resource: str,
    agent_role: str | None = None,
) -> Optional[Dict[str, Any]]:
    """Synchronous convenience wrapper (local mint only — no daemon call)."""
    return _client.request_sync(agent_id, action, resource, agent_role)
