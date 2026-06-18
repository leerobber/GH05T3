"""Holographic memory — distributed shards with reconstruction."""
from __future__ import annotations

import hashlib
import json
import math
import struct
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryShard:
    shard_id: str
    genome_id: str
    fragment: bytes
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "shard_id": self.shard_id,
            "genome_id": self.genome_id,
            "fragment_hex": self.fragment.hex(),
            "weight": self.weight,
            "metadata": self.metadata,
        }


class HolographicMemory:
    """Fractal/holographic memory store — any shard carries partial signal."""

    def __init__(self) -> None:
        self._shards: dict[str, list[MemoryShard]] = {}

    def _encode_payload(self, memory: dict[str, Any]) -> bytes:
        return json.dumps(memory, sort_keys=True).encode("utf-8")

    def _mask(self, digest: bytes, index: int, length: int) -> bytes:
        seed = hashlib.sha256(digest + struct.pack("!I", index)).digest()
        repeats = (length // len(seed)) + 1
        return (seed * repeats)[:length]

    def shard_memory(
        self,
        genome_id: str,
        memory: dict[str, Any],
        shard_count: int = 4,
    ) -> list[MemoryShard]:
        """XOR holographic encoding — any full shard set reconstructs payload."""
        payload = self._encode_payload(memory)
        digest = hashlib.sha256(payload).digest()
        length = len(payload)
        masks = [self._mask(digest, i, length) for i in range(shard_count - 1)]

        xor_masks = bytes(length)
        for m in masks:
            xor_masks = bytes(a ^ b for a, b in zip(xor_masks, m))

        shards: list[MemoryShard] = []
        mem_key = digest[:8].hex()

        for i in range(shard_count - 1):
            fragment = bytes(a ^ b for a, b in zip(payload, masks[i]))
            shard_id = hashlib.sha256(fragment + struct.pack("!I", i)).hexdigest()[:12]
            shards.append(MemoryShard(
                shard_id=shard_id,
                genome_id=genome_id,
                fragment=fragment,
                weight=1.0 / shard_count,
                metadata={"index": i, "memory_key": mem_key, "memory_type": memory.get("type")},
            ))

        shards.append(MemoryShard(
            shard_id=hashlib.sha256(xor_masks).hexdigest()[:12],
            genome_id=genome_id,
            fragment=xor_masks,
            weight=1.0 / shard_count,
            metadata={"index": shard_count - 1, "memory_key": mem_key, "parity": True},
        ))

        self._shards.setdefault(genome_id, []).extend(shards)
        return shards

    def reconstruct(self, genome_id: str, min_shards: int = 2) -> list[dict[str, Any]]:
        """XOR all shards per memory_key to recover original payload."""
        shards = self._shards.get(genome_id, [])
        if len(shards) < min_shards:
            return []

        groups: dict[str, list[MemoryShard]] = {}
        for shard in shards:
            key = shard.metadata.get("memory_key", shard.shard_id)
            groups.setdefault(key, []).append(shard)

        reconstructed: list[dict[str, Any]] = []
        for mem_key, group in groups.items():
            max_len = max(len(s.fragment) for s in group)
            merged = bytes(max_len)
            for shard in group:
                padded = shard.fragment + bytes(max_len - len(shard.fragment))
                merged = bytes(a ^ b for a, b in zip(merged, padded))
            try:
                obj = json.loads(merged.decode("utf-8"))
                obj["_holographic_digest"] = mem_key
                obj["_shard_coverage"] = len(group)
                reconstructed.append(obj)
            except (json.JSONDecodeError, UnicodeDecodeError):
                reconstructed.append({
                    "type": "fragment",
                    "_holographic_digest": mem_key,
                    "bytes": len(merged),
                })
        return reconstructed

    def qualia_from_shards(self, genome_id: str) -> dict[str, float]:
        """Derive aggregate qualia heatmap from shard weights."""
        shards = self._shards.get(genome_id, [])
        if not shards:
            return {}
        total_w = sum(s.weight for s in shards)
        curiosity = min(1.0, math.log1p(len(shards)) / 3)
        awe = min(1.0, total_w)
        return {
            "curiosity": round(curiosity, 3),
            "awe": round(awe, 3),
            "joy": round(min(1.0, len(shards) * 0.05), 3),
        }

    def state(self) -> dict[str, Any]:
        return {
            "genomes": list(self._shards.keys()),
            "total_shards": sum(len(v) for v in self._shards.values()),
        }


_holo: HolographicMemory | None = None


def get_holographic_memory() -> HolographicMemory:
    global _holo
    if _holo is None:
        _holo = HolographicMemory()
    return _holo