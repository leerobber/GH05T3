"""Registry bridge — genome sync unit tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from oss.adapters import registry as registry_mod
from oss.adapters.registry import (
    manifest_to_traits,
    sync_from_registry,
    sync_specialists_only,
)
from oss.dna.store import GenomeStore, SEED_NAMES, SEED_TRAITS


@pytest.fixture
def genome_store(tmp_path):
    """Isolated genome DB — never touches oss/data/genomes.db."""
    return GenomeStore(db_path=tmp_path / "test_genomes.db")


def _registry_ids(store: GenomeStore) -> list[str]:
    return [g.registry_agent_id for g in store.list_all()]


def test_manifest_to_traits_infers_from_category_and_tags():
    manifest = {
        "id": "oracle",
        "category": "site",
        "tags": ["research", "oracle", "intel"],
        "description": "Research and analysis specialist for sovereign memory retrieval.",
        "display_name": "Oracle Agent",
    }
    traits = manifest_to_traits(manifest)

    assert "creativity" in traits
    assert "research" in traits
    assert traits["creativity"] >= 0.62
    assert traits["research"] >= 0.70


def test_manifest_to_traits_contractor_ops_boost():
    manifest = {
        "id": "invoice",
        "category": "contractor",
        "tags": ["ops", "invoice", "workflow"],
        "description": "Handles contractor invoicing and deployment schedules.",
    }
    traits = manifest_to_traits(manifest)

    assert "ops" in traits
    assert traits["ops"] >= 0.66


def test_sync_specialists_creates_genomes(genome_store, monkeypatch):
    """Creates specialist genomes from registry manifests or SEED fallback."""

    def _mock_manifest(slug: str) -> dict | None:
        if slug.upper() not in SEED_TRAITS:
            return None
        return {
            "id": slug.lower(),
            "display_name": SEED_NAMES.get(slug.upper(), slug),
            "description": f"{slug} specialist — coding and security research.",
            "category": "general",
            "tags": [slug.lower(), "research"],
        }

    monkeypatch.setattr(registry_mod, "get_registry_manifest", _mock_manifest)

    result = sync_specialists_only(genome_store)

    assert result["errors"] == 0
    assert result["synced"] == len(SEED_TRAITS)
    assert set(_registry_ids(genome_store)) == set(SEED_TRAITS.keys())


def test_sync_specialists_without_registry_uses_seed_fallback(genome_store, monkeypatch):
    """When agent_registry/site_agents unavailable, fallback manifests still sync."""

    monkeypatch.setattr(registry_mod, "get_registry_manifest", lambda _slug: None)

    result = sync_specialists_only(genome_store)

    assert result["errors"] == 0
    assert result["synced"] == len(SEED_TRAITS)
    oracle = genome_store.get_by_registry("ORACLE")
    assert oracle is not None
    assert oracle.registry_agent_id == "ORACLE"


def test_sync_is_idempotent(genome_store, monkeypatch):
    monkeypatch.setattr(registry_mod, "get_registry_manifest", lambda _slug: None)

    first = sync_specialists_only(genome_store)
    count_after_first = len(genome_store.list_all())

    second = sync_specialists_only(genome_store)
    count_after_second = len(genome_store.list_all())

    assert first["synced"] == len(SEED_TRAITS)
    assert second["skipped"] == len(SEED_TRAITS)
    assert second["synced"] == 0
    assert count_after_first == count_after_second == len(SEED_TRAITS)
    assert len(_registry_ids(genome_store)) == len(set(_registry_ids(genome_store)))


def test_get_by_registry_links_oracle_slug(genome_store, monkeypatch):
    monkeypatch.setattr(
        registry_mod,
        "get_registry_manifest",
        lambda slug: {
            "id": "oracle",
            "display_name": "Iris Chen",
            "description": "Sovereign memory and research oracle.",
            "category": "general",
            "tags": ["oracle", "research", "math"],
        }
        if slug.upper() == "ORACLE"
        else None,
    )

    sync_specialists_only(genome_store)

    oracle = genome_store.get_by_registry("ORACLE")
    assert oracle is not None
    assert oracle.registry_agent_id == "ORACLE"
    assert oracle.display_name == "Iris Chen"
    assert "research" in oracle.traits
    assert oracle.traits["research"].value >= SEED_TRAITS["ORACLE"]["research"]


def test_sync_from_registry_with_mocked_agents(genome_store, monkeypatch):
    agents = [
        {
            "id": "oracle",
            "display_name": "Iris Chen",
            "description": "Research oracle for intel and analytics.",
            "category": "site",
            "tags": ["oracle", "research"],
        },
        {
            "id": "forge",
            "display_name": "Marcus Reid",
            "description": "Senior software engineer and code generator.",
            "category": "custom",
            "tags": ["coding", "developer"],
        },
    ]

    import agent_registry

    monkeypatch.setattr(agent_registry, "seed_builtins", lambda: 0)
    monkeypatch.setattr(agent_registry, "list_agents", lambda **kwargs: agents)

    result = sync_from_registry(genome_store)

    assert result["errors"] == 0
    assert result["synced"] == 2
    assert genome_store.get_by_registry("ORACLE") is not None
    assert genome_store.get_by_registry("FORGE") is not None


def test_sync_from_registry_idempotent(genome_store, monkeypatch):
    agents = [
        {
            "id": "oracle",
            "display_name": "Iris Chen",
            "description": "Research oracle.",
            "category": "general",
            "tags": ["oracle"],
        },
    ]

    import agent_registry

    monkeypatch.setattr(agent_registry, "seed_builtins", lambda: 0)
    monkeypatch.setattr(agent_registry, "list_agents", lambda **kwargs: agents)

    first = sync_from_registry(genome_store)
    second = sync_from_registry(genome_store)

    assert first["synced"] == 1
    assert second["skipped"] == 1
    assert len(genome_store.list_all()) == 1