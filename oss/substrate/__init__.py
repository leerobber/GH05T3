"""OSS substrate — genomes, roles, fields, value flow."""
from oss.substrate.genomic import (
    AgentHandle,
    CapabilityDescriptor,
    GenomeId,
    GenomeSegment,
    GenomicSubstrate,
    get_genomic_substrate,
    query_genome,
)
from oss.substrate.interaction_field import InteractionField, get_interaction_field
from oss.substrate.species_registry import SpeciesRegistry, get_species_registry
from oss.substrate.value_flow import ValueFlowEngine, get_value_flow

__all__ = [
    "GenomeId", "CapabilityDescriptor", "GenomeSegment", "AgentHandle",
    "GenomicSubstrate", "get_genomic_substrate", "query_genome",
    "SpeciesRegistry", "get_species_registry",
    "InteractionField", "get_interaction_field",
    "ValueFlowEngine", "get_value_flow",
]