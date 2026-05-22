"""SovereignCore Economy Client — GH05T3 integration layer.

GH05T3 is a first-class node in the SovereignNation / SovereignCore economy.
This module provides:

  - Inference routing through the SovereignCore heterogeneous compute gateway
    (RTX 5050 → Radeon 780M → Ryzen 7 CPU, all via Ollama)
  - Live economy metrics injected into every GH05T3 system prompt
  - Aegis-Vault semantic ledger registration for KAIROS cycles and key events
  - WebSocket event bus bridge so GH05T3 emits to the SovereignCore event stream

Environment variables:
  SOVEREIGN_CORE_URL   Base URL of the SovereignCore gateway  (default: http://localhost:8000)
  SOVEREIGN_API_KEY    Optional Bearer token for authenticated gateways

Port map (no conflicts):
  8000 — SovereignCore gateway
  8001 — GH05T3 backend (this service)
  8002 — GH05T3 gateway_v3
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

LOG = logging.getLogger("ghost.sovereign")

_BASE_URL: str | None = None  # cached after first read


def _sovereign_url() -> str:
    global _BASE_URL
    if _BASE_URL is None:
        _BASE_URL = os.environ.get("SOVEREIGN_CORE_URL", "http://localhost:8000").rstrip("/")
    return _BASE_URL


def _headers() -> dict[str, str]:
    key = os.environ.get("SOVEREIGN_API_KEY", "")
    h: dict[str, str] = {"Content-Type": "application/json"}
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


# ---------------------------------------------------------------------------
# Health / availability
# ---------------------------------------------------------------------------

async def sovereign_available() -> bool:
    """True if the SovereignCore gateway is reachable."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{_sovereign_url()}/health", headers=_headers())
            return r.status_code == 200
    except Exception:
        return False


async def sovereign_health() -> dict:
    """Return the full /health payload, or a degraded stub."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{_sovereign_url()}/health", headers=_headers())
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        LOG.debug("sovereign_health failed: %s", e)
    return {"status": "unreachable", "backends_healthy": 0, "backends_total": 0}


# ---------------------------------------------------------------------------
# Inference — OpenAI-compatible endpoint
# ---------------------------------------------------------------------------

async def sovereign_chat(system: str, user: str,
                         model: str = "qwen2.5:0.5b",
                         timeout: float = 60.0) -> str:
    """Route a chat request through SovereignCore's /v1/chat/completions.

    This hits the local GPU cluster (RTX 5050 → Radeon 780M → Ryzen 7 CPU)
    via Ollama.  Falls back gracefully if the gateway is unreachable.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(
                f"{_sovereign_url()}/v1/chat/completions",
                headers=_headers(),
                json={"model": model, "messages": messages, "temperature": 0.6},
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        LOG.warning("sovereign_chat failed (%s): %s", model, e)
        raise RuntimeError(f"SovereignCore gateway unavailable: {e}") from e


# ---------------------------------------------------------------------------
# Economy metrics — inject into GH05T3 system prompt
# ---------------------------------------------------------------------------

async def load_sovereign_economy_context() -> str:
    """Fetch live SovereignCore economy metrics for system prompt injection.

    Returns a compact text block like:
        [SovereignCore Economy]
        Gateway: healthy (3/3 backends)
        KAIROS: 47 elite cycles, last score 0.91
        Ledger: 1234 entries (Aegis-Vault)
        Uptime: 3721s
    Returns empty string if gateway is unreachable (no prompt pollution).
    """
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            health_r = await c.get(f"{_sovereign_url()}/health", headers=_headers())
            if health_r.status_code != 200:
                return ""
            h = health_r.json()

        lines = [
            f"Gateway: {h.get('status', 'unknown')} "
            f"({h.get('backends_healthy', 0)}/{h.get('backends_total', 0)} backends)",
        ]

        # Fetch ledger tail count
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                led_r = await c.get(f"{_sovereign_url()}/ledger/tail?n=1",
                                    headers=_headers())
                if led_r.status_code == 200:
                    total = led_r.json().get("total", 0)
                    lines.append(f"Ledger: {total} entries (Aegis-Vault)")
        except Exception:
            pass

        # Fetch KAIROS leaderboard
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                kai_r = await c.get(f"{_sovereign_url()}/kairos/leaderboard",
                                    headers=_headers())
                if kai_r.status_code == 200:
                    kd = kai_r.json()
                    elite = kd.get("elite_count", kd.get("total_cycles", 0))
                    top_score = kd.get("top_score", kd.get("best_score", 0))
                    lines.append(f"KAIROS: {elite} elite cycles, top score {top_score:.2f}")
        except Exception:
            pass

        if h.get("uptime_s"):
            lines.append(f"Uptime: {int(h['uptime_s'])}s")

        return "[SovereignCore Economy]\n" + "\n".join(lines)
    except Exception as e:
        LOG.debug("load_sovereign_economy_context failed: %s", e)
        return ""


# ---------------------------------------------------------------------------
# Aegis-Vault ledger registration
# ---------------------------------------------------------------------------

async def register_kairos_cycle(cycle: dict) -> bool:
    """Submit a completed KAIROS cycle to the SovereignCore Aegis-Vault ledger."""
    payload = {
        "source": "gh05t3",
        "event_type": "kairos_cycle",
        "data": {
            "cycle_num":   cycle.get("cycle_num"),
            "final_score": cycle.get("final_score"),
            "verdict":     cycle.get("verdict"),
            "elite":       cycle.get("elite"),
            "proposal":    cycle.get("proposal", "")[:200],
        },
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.post(
                f"{_sovereign_url()}/ledger/register",
                headers=_headers(),
                json=payload,
            )
            return r.status_code in (200, 201, 204)
    except Exception as e:
        LOG.debug("register_kairos_cycle failed: %s", e)
        return False


async def register_event(event_type: str, data: dict[str, Any]) -> bool:
    """Register any GH05T3 event with the SovereignCore Aegis-Vault ledger."""
    payload = {"source": "gh05t3", "event_type": event_type, "data": data}
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.post(
                f"{_sovereign_url()}/ledger/register",
                headers=_headers(),
                json=payload,
            )
            return r.status_code in (200, 201, 204)
    except Exception as e:
        LOG.debug("register_event(%s) failed: %s", event_type, e)
        return False


# ---------------------------------------------------------------------------
# Event bus bridge
# ---------------------------------------------------------------------------

async def emit_to_sovereign(event_name: str, payload: dict[str, Any]) -> bool:
    """Emit a GH05T3 event to the SovereignCore WebSocket event bus via REST.

    SovereignCore's /ws/events is a WebSocket; we use the REST bridge at
    /ws/emit if present, or fall back silently.
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.post(
                f"{_sovereign_url()}/ws/emit",
                headers=_headers(),
                json={"event": event_name, "source": "gh05t3", "payload": payload},
            )
            return r.status_code in (200, 201, 204)
    except Exception as e:
        LOG.debug("emit_to_sovereign(%s) failed: %s", event_name, e)
        return False


# ---------------------------------------------------------------------------
# Ledger tail (read)
# ---------------------------------------------------------------------------

async def get_ledger_tail(n: int = 20) -> list[dict]:
    """Fetch the last *n* Aegis-Vault ledger entries from SovereignCore."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{_sovereign_url()}/ledger/tail?n={n}",
                            headers=_headers())
            if r.status_code == 200:
                return r.json().get("entries", [])
    except Exception as e:
        LOG.debug("get_ledger_tail failed: %s", e)
    return []


# ---------------------------------------------------------------------------
# Startup registration
# ---------------------------------------------------------------------------

async def announce_startup(instance_url: str, instance_label: str) -> bool:
    """Tell SovereignCore that this GH05T3 node is online."""
    return await register_event("gh05t3_online", {
        "instance_url":   instance_url,
        "instance_label": instance_label,
        "version":        "0.2.0",
    })
