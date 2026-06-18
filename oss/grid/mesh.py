"""Mesh Layer facade — canonical peer contract for OSS consumers."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from oss.schemas.mesh import MeshSnapshot, PeerRecord, PeerStatus

LOG = logging.getLogger("oss.grid.mesh")

_GATEWAY = os.environ.get("GH05T3_GATEWAY_URL", "http://localhost:8002").rstrip("/")


def _auth_headers() -> dict[str, str]:
    token = os.environ.get("GH05T3_API_TOKEN", "")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def fetch_gateway_mesh(timeout: float = 4.0) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{_GATEWAY}/peers", headers=_auth_headers())
            if r.status_code == 200:
                return r.json()
    except Exception as exc:
        LOG.debug("gateway mesh fetch failed: %s", exc)
    return {"peers": [], "self": {}}


def mesh_snapshot() -> MeshSnapshot:
    """Return normalized mesh state from the live gateway contract."""
    raw = fetch_gateway_mesh()
    snap = MeshSnapshot.from_gateway_contract(raw)
    if "tailscale_configured" in raw:
        snap.tailscale_configured = bool(raw["tailscale_configured"])
    return snap


def list_peers() -> list[PeerRecord]:
    return mesh_snapshot().peers


def peer_count(online_only: bool = False) -> int:
    peers = list_peers()
    if not online_only:
        return len(peers)
    return sum(1 for p in peers if p.status == PeerStatus.ONLINE)