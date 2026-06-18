"""Registry adapter — Genome Layer ↔ agent_registry sync."""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any

from oss.dna.omni_dna import OmniDNA
from oss.dna.store import GenomeStore, SEED_NAMES, SEED_TRAITS, get_store
from oss.schemas.genome import DNAType, Trait

LOG = logging.getLogger("oss.adapter.registry")

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_SPECIALIST_IDS = frozenset(SEED_TRAITS.keys())

_CATEGORY_TRAITS: dict[str, dict[str, float]] = {
    "contractor": {"ops": 0.62, "self_reflection": 0.52},
    "site": {"creativity": 0.62, "research": 0.55},
    "business": {"ops": 0.58, "research": 0.54, "math": 0.48},
    "general": {"self_reflection": 0.50},
    "custom": {"self_reflection": 0.48, "creativity": 0.45},
}

_KEYWORD_TRAITS: list[tuple[str, str, float]] = [
    ("coding", r"\b(code|coding|coder|developer|engineer|python|rust|api|software|devops|program)\b", 0.68),
    ("research", r"\b(research|analyze|analysis|insight|study|investigate|oracle|intel)\b", 0.70),
    ("math", r"\b(math|analytics|metric|statistics|calculate|forecast|model)\b", 0.65),
    ("security", r"\b(security|sentinel|audit|vuln|cve|scan|threat|compliance)\b", 0.72),
    ("ops", r"\b(ops|operation|schedule|deploy|workflow|nexus|invoice|quote)\b", 0.66),
    ("creativity", r"\b(creative|design|content|marketing|brand|write|copy|seo)\b", 0.67),
    ("self_reflection", r"\b(plan|strategy|reflect|meta|coordinate|orchestrat)\b", 0.60),
]


def _normalize_registry_id(agent_id: str) -> str:
    return agent_id.strip().upper()


def _merge_trait_maps(*maps: dict[str, float]) -> dict[str, float]:
    merged: dict[str, float] = {}
    for trait_map in maps:
        for name, value in trait_map.items():
            merged[name] = max(merged.get(name, 0.0), float(value))
    return merged


def manifest_to_traits(manifest: dict) -> dict[str, float]:
    """Infer trait weights from registry manifest category, tags, and description."""
    traits: dict[str, float] = {}
    category = str(manifest.get("category") or "general").lower()
    for name, value in _CATEGORY_TRAITS.get(category, _CATEGORY_TRAITS["general"]).items():
        traits[name] = value

    tags = manifest.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tag_blob = " ".join(str(t) for t in tags).lower()

    desc = str(manifest.get("description") or "").lower()
    display = str(manifest.get("display_name") or manifest.get("name") or "").lower()
    agent_id = str(manifest.get("id") or "").lower()
    blob = f"{agent_id} {display} {desc} {tag_blob}"

    for trait_name, pattern, boost in _KEYWORD_TRAITS:
        if re.search(pattern, blob, re.IGNORECASE):
            traits[trait_name] = max(traits.get(trait_name, 0.0), boost)
        for tag in tags:
            if trait_name in str(tag).lower().replace("-", "_").replace(" ", "_"):
                traits[trait_name] = max(traits.get(trait_name, 0.0), boost * 0.95)

    return {k: round(min(1.0, max(0.0, v)), 4) for k, v in traits.items()}


def get_registry_manifest(registry_agent_id: str) -> dict | None:
    """Fetch agent manifest from backend registry by slug (case-insensitive)."""
    try:
        from agent_registry import get_agent
    except Exception as exc:
        LOG.warning("agent_registry import failed: %s", exc)
        return None

    for slug in (registry_agent_id, registry_agent_id.lower(), registry_agent_id.upper()):
        manifest = get_agent(slug)
        if manifest:
            return manifest
    return None


def _traits_for_agent(manifest: dict, registry_id: str) -> dict[str, float]:
    inferred = manifest_to_traits(manifest)
    seed = SEED_TRAITS.get(registry_id, {})
    return _merge_trait_maps(inferred, seed)


def _display_name_for(manifest: dict, registry_id: str) -> str:
    return (
        manifest.get("display_name")
        or manifest.get("name")
        or SEED_NAMES.get(registry_id)
        or registry_id
    )


def _sync_manifest(
    store: GenomeStore,
    manifest: dict,
    *,
    registry_id: str | None = None,
) -> dict[str, Any]:
    rid = _normalize_registry_id(registry_id or manifest.get("id") or "")
    if not rid:
        raise ValueError("manifest missing agent id")

    display_name = _display_name_for(manifest, rid)
    existing = store.get_by_registry(rid)

    if existing:
        if display_name and existing.display_name != display_name:
            existing.display_name = display_name
            store.save(existing)
            return {"registry_agent_id": rid, "action": "updated", "genome_id": existing.genome_id}
        return {"registry_agent_id": rid, "action": "skipped", "genome_id": existing.genome_id}

    trait_map = _traits_for_agent(manifest, rid)
    if not trait_map:
        trait_map = {"self_reflection": 0.5}

    dna = OmniDNA(
        registry_agent_id=rid,
        display_name=display_name,
        traits={
            name: Trait(name, value, DNAType.GENETIC)
            for name, value in trait_map.items()
        },
    )
    dna.genome_id = dna.unique_id
    record = store.save(dna)
    return {"registry_agent_id": rid, "action": "created", "genome_id": record.genome_id}


def _empty_sync_result() -> dict[str, Any]:
    return {"synced": 0, "skipped": 0, "errors": 0, "details": []}


def sync_from_registry(store: GenomeStore | None = None) -> dict[str, Any]:
    """Sync all active registry agents into genomes.db."""
    store = store or get_store()
    result = _empty_sync_result()

    try:
        from agent_registry import list_agents, seed_builtins
    except Exception as exc:
        LOG.warning("agent_registry import failed: %s", exc)
        result["errors"] += 1
        result["details"].append({"action": "error", "error": str(exc)})
        return result

    try:
        seed_builtins()
        agents = list_agents(status="active", limit=500)
    except Exception as exc:
        LOG.warning("registry listing failed: %s", exc)
        result["errors"] += 1
        result["details"].append({"action": "error", "error": str(exc)})
        return result

    for manifest in agents:
        rid = _normalize_registry_id(manifest.get("id", ""))
        if not rid:
            result["errors"] += 1
            result["details"].append({"action": "error", "error": "missing id"})
            continue
        try:
            detail = _sync_manifest(store, manifest, registry_id=rid)
            result["details"].append(detail)
            if detail["action"] == "skipped":
                result["skipped"] += 1
            else:
                result["synced"] += 1
        except Exception as exc:
            LOG.warning("sync failed for %s: %s", rid, exc)
            result["errors"] += 1
            result["details"].append({
                "registry_agent_id": rid,
                "action": "error",
                "error": str(exc),
            })

    LOG.info(
        "registry sync complete: synced=%d skipped=%d errors=%d",
        result["synced"],
        result["skipped"],
        result["errors"],
    )
    return result


def sync_specialists_only(store: GenomeStore | None = None) -> dict[str, Any]:
    """Sync the six core specialists; SEED_TRAITS fills gaps when registry row is absent."""
    store = store or get_store()
    result = _empty_sync_result()

    try:
        from agent_registry import seed_builtins
        seed_builtins()
    except Exception as exc:
        LOG.debug("seed_builtins skipped: %s", exc)

    for specialist_id in sorted(_SPECIALIST_IDS):
        manifest = get_registry_manifest(specialist_id)
        if manifest is None:
            manifest = {
                "id": specialist_id.lower(),
                "display_name": SEED_NAMES.get(specialist_id, specialist_id),
                "description": f"{specialist_id} specialist",
                "category": "general",
                "tags": [specialist_id.lower()],
            }
        try:
            detail = _sync_manifest(store, manifest, registry_id=specialist_id)
            result["details"].append(detail)
            if detail["action"] == "skipped":
                result["skipped"] += 1
            else:
                result["synced"] += 1
        except Exception as exc:
            LOG.warning("specialist sync failed for %s: %s", specialist_id, exc)
            result["errors"] += 1
            result["details"].append({
                "registry_agent_id": specialist_id,
                "action": "error",
                "error": str(exc),
            })

    LOG.info(
        "specialist sync complete: synced=%d skipped=%d errors=%d",
        result["synced"],
        result["skipped"],
        result["errors"],
    )
    return result


def registry_status(store: GenomeStore | None = None) -> dict[str, Any]:
    """Compare genome records against active registry agents."""
    store = store or get_store()

    try:
        from agent_registry import list_agents, registry_stats, seed_builtins
    except Exception as exc:
        LOG.warning("agent_registry import failed: %s", exc)
        return {"error": str(exc), "genome_count": len(store.list_all())}

    seed_builtins()
    agents = list_agents(status="active", limit=500)
    registry_slugs = {_normalize_registry_id(a["id"]) for a in agents}
    genomes = store.list_all()
    genome_slugs = {_normalize_registry_id(g.registry_agent_id) for g in genomes}
    linked = registry_slugs & genome_slugs

    return {
        "registry": registry_stats(),
        "genome_count": len(genomes),
        "registry_active_count": len(registry_slugs),
        "linked_count": len(linked),
        "unlinked_genomes": sorted(genome_slugs - registry_slugs),
        "unlinked_registry_agents": sorted(registry_slugs - genome_slugs),
    }