"""Unknown-data territory map — multi-domain scientific + exotic ingest."""
from __future__ import annotations

from oss.kernel.schemas import DataTerritory, DataTerritoryClass

# Foundational sciences → OSS Forge domains; exotic → ingest path stubs
TERRITORIES: tuple[DataTerritory, ...] = (
    DataTerritory("physics", "Theoretical Physics", DataTerritoryClass.STRUCTURED_SCIENCE,
                  "theoretical_physics_and_complexity"),
    DataTerritory("chemistry", "Reaction Networks & Materials", DataTerritoryClass.STRUCTURED_SCIENCE,
                  "computational_science", ("backend/data/training/",)),
    DataTerritory("biology", "Genomics & Bio-Inspired AI", DataTerritoryClass.STRUCTURED_SCIENCE,
                  "genomics_inspired_ai"),
    DataTerritory("materials", "Materials Science", DataTerritoryClass.STRUCTURED_SCIENCE,
                  "computational_science"),
    DataTerritory("mathematics", "Pure & Applied Mathematics", DataTerritoryClass.STRUCTURED_SCIENCE,
                  "theoretical_computer_science"),
    DataTerritory("economics", "Economic Systems", DataTerritoryClass.ECONOMIC,
                  "mycological_network_economics", ("training_data/domain_research/",)),
    DataTerritory("systems", "Systems & Complexity", DataTerritoryClass.STRUCTURED_SCIENCE,
                  "systems_engineering"),
    DataTerritory("ml_theory", "Machine Learning Theory", DataTerritoryClass.STRUCTURED_SCIENCE,
                  "machine_learning_theory"),
    DataTerritory("simulation", "Computational Simulations", DataTerritoryClass.SYNTHETIC,
                  "computational_science", synthetic=True),
    DataTerritory("sensor_raw", "Raw Sensor Streams", DataTerritoryClass.UNSTRUCTURED_EXOTIC),
    DataTerritory("satellite", "Satellite Imagery", DataTerritoryClass.UNSTRUCTURED_EXOTIC),
    DataTerritory("climate", "Climate Simulations", DataTerritoryClass.UNSTRUCTURED_EXOTIC),
    DataTerritory("molecular_dynamics", "Molecular Dynamics", DataTerritoryClass.UNSTRUCTURED_EXOTIC),
    DataTerritory("astrophysical", "Astrophysical Simulations", DataTerritoryClass.UNSTRUCTURED_EXOTIC,
                  "theoretical_physics_and_complexity"),
    DataTerritory("genomic", "Genomic Sequences", DataTerritoryClass.UNSTRUCTURED_EXOTIC,
                  "genomics_inspired_ai"),
    DataTerritory("economic_ts", "Economic Time-Series", DataTerritoryClass.ECONOMIC,
                  "statistical_inference_science", ("data/spin_dataset.jsonl",)),
    DataTerritory("agent_abm", "Agent-Based Simulations", DataTerritoryClass.AGENT_SIM,
                  "agentic_systems_science"),
    DataTerritory("frontier_unknown", "Frontier Unknown Sciences", DataTerritoryClass.SYNTHETIC,
                  "frontier_unknown_sciences", synthetic=True),
)


def list_territories() -> list[dict]:
    return [t.to_dict() for t in TERRITORIES]


def territory_for_tick(tick: int) -> DataTerritory:
    return TERRITORIES[tick % len(TERRITORIES)]