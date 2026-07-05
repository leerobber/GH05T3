# Inventory: four parallel evolution/genome systems

**Status:** Reference — documents a real, unresolved duplication, not a decision

## Context

Across this repo and two sibling repos, the same underlying idea
(genetic-algorithm-style evolution of agents/architectures, scored against
a reward/fitness function) has been built four separate times,
independently, with no communication between any of them beyond
sovereign-core's HTTP health-probe registry.

## The four systems

| System | Repo | Where | What |
|---|---|---|---|
| MVS / OmniDNA | `GH05T3` (`main`) | `backend/oss/mvs.py`, `backend/oss/genomic_substrate.py`, `oss/dna/omni_dna.py` + `backend/oss/omni_dna.py`, `oss/schemas/genome.py` | The most mature — `GenomicSubstrate`, `OmniMind`, `OmniEconomy`, `SpeciesMemory`, `SpeciationEngine`, `OmniNet`, `MetaLearningEngine`, `SelfImprovingLoopV2`, plus an `OmniFinancialSector` (liquidity routing, auto-disabled by a safety engine — see the `# AUTO-DISABLED by GH05T3 aggressive engine` comment in `backend/gateway_v3.py`). Already documented in `docs/details/canonical-paths.md`'s "Genomic / MVS Layer" table. |
| `oss/ecosystem` species-FSM + economy | `GH05T3` (`main`) | `oss/ecosystem/{fsm,orchestrator,rewards,store,bootstrap}.py` | A separate 7-state species FSM + 5 role FSMs + Omni-Mind/Omni-Economy FSMs, real reward math, now wired to real telemetry — see [oss-ecosystem-live-telemetry.md](oss-ecosystem-live-telemetry.md). **Not** in the canonical-paths.md MVS table — a real documentation gap, now partially closed by this file. |
| 5-trait genome subsystem | `GH05T3-Sovereign` | `backend/oss/{dna,core,api}/` | `binary_ratio`, `stabilizer`, `out_proj_quant_mode`, `mainbl_threshold`, `ternary_sparsity_target` — architecture/quantization traits for the binary/ternary transformer, not agent personas. Built from `GH05T3`'s `claude/fix-multi-gpu-training-2WHKH` branch, which diverged from `main` on 2026-05-22 — before MVS/OmniDNA and `oss/ecosystem` existed on that branch. Built independently, not because MVS was rejected. |
| KAIROS / DGM | `sovereign-core` | `kairos/`, `gateway/kairos_routes.py` | A separate Proposer→Critic→Verifier→Meta-Agent self-improvement loop, its own economy modules, on a different physical repo/brand (SovereignNation, AGPL). |

## Why this happened

The `GH05T3-Sovereign` case is the clearest root cause: it was built from a
feature branch (`claude/fix-multi-gpu-training-2WHKH`) that had already
diverged from `main` by 133 commits (as of this writing) before that
branch's own genome work started — the richer MVS/OmniDNA and
`oss/ecosystem` systems on `main` simply weren't visible from where the
fork happened. `sovereign-core`'s KAIROS is a separate case: a
deliberately separate commercial product built on the same physical
hardware, not a fork of this repo at all.

## Consequences / open item

Not resolved here. Real options, in rough order of effort: (a) fold the
5-trait system into MVS/OmniDNA's `GenomicSubstrate` as additional trait
types rather than a separate substrate, (b) merge or retire the
`claude/fix-multi-gpu-training-2WHKH` branch so this class of
"built from a stale fork" duplication stops recurring, (c) leave all four
as deliberately separate and only connect them via HTTP (the pattern
`sovereign-core`'s `registry.py` already uses for `gh05t3` and
`gh05t3_sovereign`). No decision has been made between these.
