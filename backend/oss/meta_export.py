"""
Meta-evolution data exporter (MVS only path)

Collects from the single source of truth:
- traits
- fitness
- memories (phenomenal)
- neurocoins
- mutations

This data trains the next version of the species.
"""

from __future__ import annotations
from typing import List, Dict, Any
import json
from pathlib import Path

def collect_meta_samples(substrate, mind, economy) -> List[Dict[str, Any]]:
    samples = []
    for genome_id, rec in getattr(substrate, 'genomes', {}).items():
        dna = rec.dna if hasattr(rec, 'dna') else None
        if not dna:
            continue
        traits = dna.get_traits()
        fitness_history = getattr(rec, 'fitness_history', [])
        balance = economy.get_balance(genome_id) if hasattr(economy, 'get_balance') else 0.0
        memories = getattr(dna, 'phenomenal_memory', [])[-20:]

        is_theorist = getattr(dna, 'role', '') == "THEORIST_ELITE"
        canonical_memories = [m for m in memories if m.get("canonical")]
        theory_lab_cycles = [m.get("theory_lab_cycle") for m in memories if m.get("theory_lab_cycle") is not None]

        samples.append({
            "genome_id": genome_id,
            "role": getattr(dna, 'role', rec.role if hasattr(rec, 'role') else ''),
            "is_theorist": is_theorist,
            "traits": traits,
            "fitness_history": fitness_history,
            "neurocoins": balance,
            "recent_memories": memories,
            "canonical_memories": canonical_memories,
            "theory_lab_cycles": theory_lab_cycles,
            # placeholders for scores - populate from lab when logging
            "theory_depth_score": None,
            "coherence_score": None,
            "novelty_score": None,
            "harm_score": None,
        })
    return samples

def export_meta_evolution_jsonl(samples: List[Dict[str, Any]], path: str = "data/oss_meta_evolution.jsonl"):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"Exported {len(samples)} meta-evolution samples to {path}")
