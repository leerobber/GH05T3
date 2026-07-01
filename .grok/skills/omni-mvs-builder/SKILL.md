---
name: omni-mvs-builder
description: >
  Phase 1 MVS builder for Omni-Sentient: OmniDNA, GenomicSubstrate, OmniMind, OmniEconomy,
  Theory Lab, Meta-Export, tests, performance, error handling. USE WHEN: MVS, test_mvs_core,
  traits.py migration, theory lab stress test, register_genome, AgentHandle act error,
  omni_dna evolve, phase 1 gate, RNA layer. DO NOT USE FOR: VolatilityWorld v1 (Phase 2)
  or financial sector (Phase 8).
version: 1.0.0
---

# Omni MVS Builder (Phase 1)

**Non-negotiable:** No Phase 2+ features until Phase 1 gate passes.

## Canonical modules

| Component | Path |
|-----------|------|
| MVS entry | `backend/oss/mvs.py` |
| OmniDNA | `backend/oss/omni_dna.py` |
| Substrate | `backend/oss/genomic_substrate.py` |
| OmniMind | `backend/oss/omni_mind.py` |
| OmniEconomy | `backend/oss/omni_economy.py` |
| Theory Lab | `backend/oss/lab/theory_lab.py` |
| Meta-Export | `backend/oss/meta_export.py` |
| Loop | `backend/oss/loop.py` |

## Parallel path elimination

```bash
rg "from backend.oss.traits" backend/oss/
```

Migrate to `OmniDNA` only. Targets: `genomic_substrate.py`, `species_viz.py`. Delete `traits.py` when zero imports.

## Tests to create/extend

`tests/test_mvs_core.py` (create):

- `OmniDNA.evolve()` deterministic with seed
- `GenomicSubstrate.register_genome()` validation
- `OmniMind.sync()` no error
- `OmniEconomy.reward()` ledger consistency

Extend: `test_oss_dna.py`, `test_oss_economy.py`, `test_oss_mind_swarm.py`

## Stress test

```bash
cd /mnt/c/Users/leer4/GH05T3
python -m backend.oss.lab.theory_lab  # or theory_lab.py with --cycles 1000 --live False
pytest tests/test_mvs_core.py tests/test_oss_dna.py -v
```

## Performance

```bash
python -m cProfile -s cumtime -m backend.oss.loop  # or targeted act() profile
```

Targets: Week 1 <100ms/act, Week 2 <50ms p95 dry-run.

## Error handling pattern (AgentHandle.act)

```python
except Exception as e:
    self.dna.add_memory({"type": "error", "error": str(e), "task": task, ...})
    return {"agent_id": self.agent_id, "error": str(e), "fallback": True}
```

## Phase 1 gate checklist

- [ ] `test_mvs_core.py` green
- [ ] No `traits.py` imports
- [ ] 1000-cycle theory lab dry-run
- [ ] Meta-export validates
- [ ] p95 <50ms

On pass: `python scripts/omni_brain_checkpoint.py --set-phase 2 --metric traits_py_eliminated=true`