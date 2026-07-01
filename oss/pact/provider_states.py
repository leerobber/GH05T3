"""
Pact provider state setup — single canonical handler.

Mounted at POST /_pact/provider_states on the gateway (root, not under /oss).
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["pact"])


def apply_provider_state(state_name: str) -> None:
    name = (state_name or "").lower()
    if "mvs" not in name:
        return
    try:
        from oss.utils.paths import ensure_oss_paths

        ensure_oss_paths()
        from backend.oss.loop import ensure_mvs_seeded

        ensure_mvs_seeded(verbose=False)
    except Exception:
        pass


@router.post("/_pact/provider_states")
async def provider_states(state: dict) -> dict:
    apply_provider_state(state.get("state", ""))
    return {"ok": True, "result": "ok", "state": state.get("state", "")}
