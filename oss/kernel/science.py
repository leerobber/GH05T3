"""Theory engine — hypotheses, forge research, self-evaluation."""
from __future__ import annotations

import logging
from typing import Any

LOG = logging.getLogger("oss.kernel.science")


def next_research_domain(last_domain: str) -> str:
    """Rotate Rob business domains + scientific forge domains."""
    rotation = (
        "business", "sales", "growth", "ml_engineer", "frontier",
        "machine_learning_theory", "systems_engineering", "computational_science",
        "epistemology_and_discovery", "agentic_systems_science",
    )
    try:
        idx = rotation.index(last_domain)
        return rotation[(idx + 1) % len(rotation)]
    except ValueError:
        return rotation[0]


def run_research_phase(
    *,
    domain: str,
    territory_key: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Generate research signal — forge ingest manifest + optional KAIROS record."""
    result: dict[str, Any] = {
        "domain": domain,
        "territory": territory_key,
        "dry_run": dry_run,
        "hypothesis_queued": False,
    }

    try:
        from oss.forge.domains import list_domains
        result["forge_domains"] = len(list_domains())
    except Exception as exc:
        result["forge_error"] = str(exc)

    if dry_run:
        result["hypothesis"] = (
            f"Probe {territory_key} via {domain} — simulate, evaluate, iterate"
        )
        return result

    try:
        from oss.adapters.evolution import record_swarm_cycle
        proposal = f"[KERNEL] Territory {territory_key} → domain {domain} research cycle"
        rec = record_swarm_cycle(proposal, score=0.72, agent_ids=["ORACLE", "GH05T3"])
        result["kairos"] = rec
        result["hypothesis_queued"] = True
    except Exception as exc:
        LOG.warning("research phase record failed: %s", exc)
        result["error"] = str(exc)
    return result