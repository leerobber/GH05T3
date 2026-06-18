"""Mesh Layer — peer discovery and distributed node contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DiscoveryMode(str, Enum):
    TAILSCALE = "tailscale"
    LAN = "lan"
    GITHUB_RELAY = "github_relay"
    MANUAL = "manual"
    FRONTIER_BUS = "frontier_bus"


class PeerStatus(str, Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class PeerRecord:
    """Canonical peer entry for OSS mesh snapshots."""

    label: str
    url: str
    ip: str = ""
    status: PeerStatus = PeerStatus.UNKNOWN
    agents: int = 0
    version: str = ""
    discovery: DiscoveryMode = DiscoveryMode.TAILSCALE
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "url": self.url,
            "ip": self.ip,
            "status": self.status.value,
            "agents": self.agents,
            "version": self.version,
            "discovery": self.discovery.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_gateway_peer(cls, data: dict[str, Any]) -> PeerRecord:
        raw_status = str(data.get("status", "unknown")).lower()
        if raw_status in ("ok", "healthy", "online"):
            status = PeerStatus.ONLINE
        elif raw_status in ("degraded",):
            status = PeerStatus.DEGRADED
        elif raw_status in ("offline", "unreachable"):
            status = PeerStatus.OFFLINE
        else:
            status = PeerStatus.UNKNOWN
        return cls(
            label=str(data.get("label", data.get("hostname", "unknown"))),
            url=str(data.get("url", "")),
            ip=str(data.get("ip", "")),
            status=status,
            agents=int(data.get("agents", data.get("swarm_agents", 0)) or 0),
            version=str(data.get("version", "")),
            discovery=DiscoveryMode.TAILSCALE,
            metadata={k: v for k, v in data.items()
                      if k not in ("label", "url", "ip", "status", "agents", "version")},
        )


@dataclass
class MeshSnapshot:
    """Normalized mesh contract — aligns gateway /peers with OSS consumers."""

    self_node: dict[str, Any] = field(default_factory=dict)
    peers: list[PeerRecord] = field(default_factory=list)
    discovery_mode: DiscoveryMode = DiscoveryMode.TAILSCALE
    tailscale_configured: bool = False
    routes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "self": self.self_node,
            "peers": [p.to_dict() for p in self.peers],
            "count": len(self.peers),
            "discovery_mode": self.discovery_mode.value,
            "tailscale_configured": self.tailscale_configured,
            "routes": self.routes,
        }

    @classmethod
    def from_gateway_contract(cls, data: dict[str, Any]) -> MeshSnapshot:
        peers_raw = data.get("peers") or []
        peers = [PeerRecord.from_gateway_peer(p) for p in peers_raw if isinstance(p, dict)]
        mesh = data.get("mesh") or {}
        discovery = mesh.get("discovery") or {}
        routes: dict[str, str] = {}
        if isinstance(discovery, dict):
            routes["refresh"] = str(discovery.get("refresh", "/peers/refresh"))
            routes["ping"] = str(discovery.get("ping", "/peers/ping"))
        github = mesh.get("github_relay") or {}
        if isinstance(github, dict):
            for key in ("push", "pull", "sync", "peers"):
                if key in github:
                    routes[f"github_{key}"] = str(github[key])
        return cls(
            self_node=dict(data.get("self") or {}),
            peers=peers,
            discovery_mode=DiscoveryMode.TAILSCALE,
            tailscale_configured=bool(data.get("tailscale_configured")),
            routes=routes,
        )