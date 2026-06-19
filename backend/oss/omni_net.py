"""
Omni-Net Beta (v0.1) — The Network Layer for GH05T3 / Omni-OS

Minimal viable "net" for 100-500 agents:
- In-memory peer registry (easy to replace with real p2p / tailscale mesh later)
- DNA / memetic broadcast & pull
- Canonical memory gossip
- Simple weighted "net consensus" on proposals
- Trait marketplace signals across the net
- Hooks for theory_lab to "publish" successful theories

This bridges local MVS minds into a distributed species.

Usage (inside MVS code):
    from backend.oss.omni_net import OmniNet
    net = OmniNet()
    net.register(genome_id, dna, role)
    net.broadcast_theory(genome_id, proposal_text, score)
    peers = net.sample_peers(k=5)
    shared = net.pull_canonical_memories(limit=10)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import time
import random
import json
from pathlib import Path


@dataclass
class Peer:
    genome_id: str
    role: str
    traits: Dict[str, float]
    last_seen: float = field(default_factory=time.time)
    published_count: int = 0
    reputation: float = 0.5   # simple 0-1 from successful publications


class OmniNet:
    """Simple in-memory network for the MVS. Later: real transport + auth."""

    PERSIST_PATH = Path(__file__).resolve().parents[2] / "data" / "omni_net_state.json"

    def __init__(self, max_peers: int = 500, persist: bool = True):
        self.max_peers = max_peers
        self.peers: Dict[str, Peer] = {}
        self.theory_feed: List[Dict[str, Any]] = []
        self.canonical_gossip: List[Dict[str, Any]] = []
        self._last_prune = time.time()
        self.persist = persist
        if persist:
            self._load()

    # ---------------- Registration ----------------
    def register(self, genome_id: str, role: str, traits: Dict[str, float]) -> Peer:
        if genome_id in self.peers:
            p = self.peers[genome_id]
            p.last_seen = time.time()
            p.traits = traits
            return p
        if len(self.peers) >= self.max_peers:
            self._prune_old_peers()
        p = Peer(genome_id=genome_id, role=role, traits=dict(traits))
        self.peers[genome_id] = p
        return p

    def unregister(self, genome_id: str):
        self.peers.pop(genome_id, None)

    # ---------------- Theory Publishing (for TheoryLab) ----------------
    def broadcast_theory(self, genome_id: str, proposal: str, score: float, world: str = "unknown", meta: Optional[Dict] = None):
        """An elite theorist publishes a scored theory to the net."""
        if genome_id not in self.peers:
            return False
        peer = self.peers[genome_id]
        entry = {
            "genome_id": genome_id,
            "role": peer.role,
            "score": round(score, 4),
            "world": world,
            "proposal": proposal[:1200],   # keep bounded
            "ts": time.time(),
            "traits_snapshot": {k: round(v, 2) for k, v in list(peer.traits.items())[:6]},
            **(meta or {})
        }
        self.theory_feed.append(entry)
        if len(self.theory_feed) > 2000:
            self.theory_feed = self.theory_feed[-1500:]

        # reputation update
        if score > 0.8:
            peer.reputation = min(0.98, peer.reputation + 0.03)
        elif score < 0.5:
            peer.reputation = max(0.1, peer.reputation - 0.02)
        peer.published_count += 1
        peer.last_seen = time.time()
        if self.persist:
            self._save()
        return True

    # ---------------- Memetic / Canonical Gossip ----------------
    def publish_canonical(self, genome_id: str, memory: Dict[str, Any]):
        """Share high-value canonical memory (from Mind v1.5)."""
        if genome_id not in self.peers:
            return
        mem = dict(memory)
        mem["source"] = genome_id
        mem["ts"] = time.time()
        self.canonical_gossip.append(mem)
        if len(self.canonical_gossip) > 500:
            self.canonical_gossip = self.canonical_gossip[-350:]
        if self.persist:
            self._save()

    def pull_canonical_memories(self, limit: int = 20, min_score: float = 0.6) -> List[Dict[str, Any]]:
        """Other agents pull useful memories."""
        good = [m for m in self.canonical_gossip if m.get("computed_score", 0) >= min_score or m.get("canonical")]
        return sorted(good, key=lambda x: x.get("ts", 0), reverse=True)[:limit]

    # ---------------- Sampling & Simple Net Consensus ----------------
    def sample_peers(self, k: int = 5, role_filter: Optional[str] = None) -> List[Peer]:
        peers = list(self.peers.values())
        if role_filter:
            peers = [p for p in peers if role_filter.upper() in p.role.upper()]
        # bias toward higher reputation
        peers.sort(key=lambda p: p.reputation + random.random()*0.1, reverse=True)
        return peers[:k]

    def net_consensus(self, proposals: List[Dict[str, Any]], boost_theorists: bool = True) -> Dict[str, Any]:
        """Very lightweight network-level weighted consensus (complements local OmniMind v1.5)."""
        if not proposals:
            return {}
        total = 0.0
        acc: Dict[str, float] = {}
        for p in proposals:
            gid = p.get("genome_id", "anon")
            peer = self.peers.get(gid)
            w = (peer.reputation if peer else 0.5) + 0.3
            if boost_theorists and "THEORIST" in str(p.get("role", "")).upper():
                w *= 1.7
            if p.get("score"):
                w *= (0.5 + p["score"])
            total += w
            for k, v in p.items():
                if isinstance(v, (int, float)):
                    acc[k] = acc.get(k, 0.0) + float(v) * w
        if total <= 0:
            return {}
        return {k: round(v / total, 4) for k, v in acc.items()}

    # ---------------- Memetic Trait Spread (DNA v2) ----------------
    def memetic_spread(self, source_gid: str, target_gids: List[str], strength: float = 0.12):
        """Spread successful traits from a high-performer to others (horizontal)."""
        if source_gid not in self.peers:
            return 0
        source = self.peers[source_gid]
        spread = 0
        for gid in target_gids:
            if gid in self.peers and gid != source_gid:
                tgt = self.peers[gid]
                for t, val in source.traits.items():
                    if t in tgt.traits:
                        old = tgt.traits[t]
                        tgt.traits[t] = max(0.1, min(0.95, old * (1-strength) + val * strength))
                spread += 1
        return spread

    # ---------------- Persistence (simple for Beta) ----------------
    def _load(self):
        try:
            if self.PERSIST_PATH.exists():
                raw = json.loads(self.PERSIST_PATH.read_text(encoding="utf-8"))
                for gid, p in raw.get("peers", {}).items():
                    self.peers[gid] = Peer(**p)
                self.theory_feed = raw.get("theory_feed", [])[-1500:]
                self.canonical_gossip = raw.get("canonical_gossip", [])[-350:]
        except Exception:
            pass

    def _save(self):
        try:
            self.PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "peers": {gid: {"genome_id": p.genome_id, "role": p.role, "traits": p.traits,
                                "last_seen": p.last_seen, "published_count": p.published_count,
                                "reputation": p.reputation} for gid, p in self.peers.items()},
                "theory_feed": self.theory_feed[-1500:],
                "canonical_gossip": self.canonical_gossip[-350:],
            }
            self.PERSIST_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ---------------- Maintenance ----------------
    def _prune_old_peers(self):
        now = time.time()
        stale = [gid for gid, p in self.peers.items() if now - p.last_seen > 3600]
        for gid in stale[:max(1, len(stale)//3)]:
            self.peers.pop(gid, None)
        if self.persist:
            self._save()

    def stats(self) -> Dict[str, Any]:
        if self.persist:
            self._save()
        return {
            "peer_count": len(self.peers),
            "theories_published": len(self.theory_feed),
            "canonical_gossip": len(self.canonical_gossip),
            "top_reputation": sorted(
                [(p.genome_id, round(p.reputation, 2), p.role) for p in self.peers.values()],
                key=lambda x: -x[1]
            )[:5]
        }


# ---------- Convenience singleton for MVS / TheoryLab ----------
_global_net: Optional[OmniNet] = None

def get_omni_net() -> OmniNet:
    global _global_net
    if _global_net is None:
        _global_net = OmniNet()
    return _global_net


# ---------- Tiny demo ----------
if __name__ == "__main__":
    net = get_omni_net()
    net.register("DNA-THE-001", "THEORIST_ELITE", {"math": 0.95, "alignment": 0.92, "self_reflection": 0.9})
    net.broadcast_theory("DNA-THE-001", "Regime-aware alignment model with L_align regularizer...", score=0.91, world="AlignmentWorld")
    print("Net stats:", net.stats())
    print("Pulled canonical:", len(net.pull_canonical_memories(3)))
    print("Omni-Net Beta ready for MVS integration.")
