"""Omega DNA rewrite — high-score genomes emit self-patch manifests."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from oss.dna.omni_dna import OmniDNA
from oss.schemas.genome import Trait

REWRITE_THRESHOLD = 0.85
_MANIFEST_DIR = Path(__file__).resolve().parents[1] / "data" / "omega_manifests"


@dataclass
class PatchEntry:
    target: str
    action: str
    value: Any
    reason: str

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "action": self.action,
            "value": self.value,
            "reason": self.reason,
        }


@dataclass
class OmegaManifest:
    genome_id: str
    score: float
    patches: list[PatchEntry] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "genome_id": self.genome_id,
            "score": self.score,
            "patches": [p.to_dict() for p in self.patches],
            "created_at": self.created_at,
            "checksum": self.checksum(),
        }

    def checksum(self) -> str:
        payload = json.dumps([p.to_dict() for p in self.patches], sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


class OmegaRewriter:
    """Generate and apply omega-level DNA patch manifests."""

    def __init__(self, threshold: float = REWRITE_THRESHOLD) -> None:
        self.threshold = threshold
        _MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    def propose_manifest(self, dna: OmniDNA, score: float) -> OmegaManifest | None:
        if score < self.threshold:
            return None

        patches: list[PatchEntry] = []
        for name, trait in dna.traits.items():
            if trait.value < 0.9:
                patches.append(PatchEntry(
                    target=f"traits.{name}",
                    action="boost",
                    value=round(min(1.0, trait.value + 0.05), 4),
                    reason=f"elite score {score:.2f}",
                ))

        if dna.dna_type.name != "OMEGA":
            patches.append(PatchEntry(
                target="dna_type",
                action="set",
                value="OMEGA",
                reason="score threshold unlocks omega tier",
            ))

        meta = dna.meta_dna or {}
        recipes = list((meta.get("rewrite_recipes") or []))
        recipes.append({"score": score, "patch_count": len(patches)})
        patches.append(PatchEntry(
            target="meta_dna.rewrite_recipes",
            action="append",
            value=recipes[-5:],
            reason="track rewrite lineage",
        ))

        return OmegaManifest(
            genome_id=dna.genome_id,
            score=score,
            patches=patches,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def apply_manifest(self, dna: OmniDNA, manifest: OmegaManifest) -> list[str]:
        applied: list[str] = []
        for patch in manifest.patches:
            if patch.action == "boost" and patch.target.startswith("traits."):
                tname = patch.target.split(".", 1)[1]
                if tname in dna.traits:
                    dna.traits[tname].value = float(patch.value)
                    applied.append(patch.target)
            elif patch.target == "dna_type" and patch.action == "set":
                from oss.schemas.genome import DNAType
                dna.dna_type = DNAType[patch.value]
                applied.append(patch.target)
            elif patch.target == "meta_dna.rewrite_recipes":
                dna.meta_dna["rewrite_recipes"] = patch.value
                applied.append(patch.target)

        dna.evolution_history.append({
            "event": "omega_rewrite",
            "score": manifest.score,
            "patches": len(manifest.patches),
            "checksum": manifest.checksum(),
        })
        return applied

    def save_manifest(self, manifest: OmegaManifest) -> Path:
        path = _MANIFEST_DIR / f"{manifest.genome_id}_{manifest.checksum()}.json"
        path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
        return path

    def rewrite_if_elite(self, dna: OmniDNA, score: float) -> dict[str, Any]:
        manifest = self.propose_manifest(dna, score)
        if not manifest:
            return {"rewritten": False, "score": score, "threshold": self.threshold}
        applied = self.apply_manifest(dna, manifest)
        path = self.save_manifest(manifest)
        return {
            "rewritten": True,
            "score": score,
            "manifest": manifest.to_dict(),
            "applied": applied,
            "manifest_path": str(path),
        }