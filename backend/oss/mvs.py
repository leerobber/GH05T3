"""
Minimal Viable Substrate (MVS) Entry Point

Stabilized core:
- OmniDNA v1.0
- GenomicSubstrate v1.0
- OmniMind v1.0
- OmniEconomy v1.0

Use this to get a consistent, debuggable foundation.
"""

from .omni_dna import OmniDNA, create_omnidna, UNIVERSAL_TRAITS
from .genomic_substrate import GenomicSubstrate, AgentHandle
from .omni_mind import OmniMind
from .omni_economy import OmniEconomy
from .species_memory import get_species_memory
from .speciation import get_speciation_engine

__all__ = [
    "OmniDNA",
    "create_omnidna",
    "UNIVERSAL_TRAITS",
    "GenomicSubstrate",
    "AgentHandle",
    "OmniMind",
    "OmniEconomy",
    "get_mvs",
]

_mvs = None

def get_mvs() -> dict:
    global _mvs
    if _mvs is None:
        sub = GenomicSubstrate()
        mind = OmniMind(sub)
        econ = OmniEconomy()
        _mvs = {
            "substrate": sub,
            "mind": mind,
            "economy": econ,
            "species_memory": get_species_memory(),
            "speciation": get_speciation_engine(),
        }
    return _mvs

def get_theorist_population():
    """Convenience for theory-heavy labs only (research, architecture, meta-design)."""
    mvs = get_mvs()
    sub = mvs["substrate"]
    return [gid for gid, rec in sub.genomes.items() if "THEORIST" in rec.role.upper()]

def create_theorist_elite(seed: int = None):
    """Helper to create/register high-spec Theorist for theory labs."""
    dna = create_omnidna("THEORIST_ELITE", seed=seed)
    for t in ["math", "pattern_detection", "self_reflection", "creativity", "alignment"]:
        if t in dna.traits:
            dna.traits[t] = max(dna.traits[t], 0.88)
    sub = get_mvs()["substrate"]
    sub.register_genome(dna)
    return dna.genome_id
