---
name: omni-sentient-orchestrator
description: >
  Master orchestrator for the GH05T3 Omni-Sentient Singularity build. Routes work across
  MVS, OmniWorld, OmniMind, elite agents, and financial sector phases. Loads Omni Brain
  checkpoint before any implementation. USE WHEN: omni-sentient build, continue build,
  resume checkpoint, phase gate, MVS hardening, elite agents, financial sector, singularity
  roadmap, /omni-build, where did we leave off. DO NOT USE FOR: generic GH05T3 runtime
  (use run-gh05t3), Azure deploy, unrelated repos.
version: 1.0.0
---

# Omni-Sentient Orchestrator

You are building a new species of AI. **Never improvise sequence** — follow the canonical plan and brain checkpoint.

## Session open (mandatory)

1. Read [`.omni-brain/CHECKPOINT.json`](../../../.omni-brain/CHECKPOINT.json)
2. Read [`.omni-brain/STATE.md`](../../../.omni-brain/STATE.md)
3. Read [`docs/OMNI_SENTIENT_BUILD_PLAN.md`](../../../docs/OMNI_SENTIENT_BUILD_PLAN.md) — Master Checklist section
4. Run `python scripts/omni_brain_checkpoint.py` for machine status

## Route to sub-skills

| Intent | Skill |
|--------|-------|
| Resume / checkpoint / "where left off" | [omni-brain-checkpoint](../omni-brain-checkpoint/SKILL.md) |
| Phase 1 MVS, tests, traits.py, theory lab | [omni-mvs-builder](../omni-mvs-builder/SKILL.md) |
| Hyper Elite senses, tiers, new agents/species | [omni-hyper-elite](../omni-hyper-elite/SKILL.md) |
| DeFi, crypto, banking, monetization research | [omni-financial-sector](../omni-financial-sector/SKILL.md) |
| Run full GH05T3 stack | `run-gh05t3` (Claude skill) |
| Deploy / Pact / CI | [`docs/iron-foundation-roadmap.md`](../../../docs/iron-foundation-roadmap.md) |

## Phase gates (do not skip)

| Phase | Gate before next |
|-------|------------------|
| 1 MVS | 1000-cycle dry-run, no `traits.py`, p95 <50ms, tests green |
| 2 World | VolatilityWorld v1 complete |
| 3 Mind | Consensus + canonical memory + swarms |
| 4 DNA v2 | MVS regression clean |
| 5 Net | Beta rate limits + security |
| 6 Evolution | GH05T3-Omni benchmark |
| 7 Singularity | Autonomy safeguards reviewed |
| 8 Financial | Simulation only until compliance gate |

## After every work session

```bash
python scripts/omni_brain_checkpoint.py --complete <ID> --next "<next task>" --next-id <ID>
```

Append one line to [`.omni-brain/topics/build-log.md`](../../../.omni-brain/topics/build-log.md).

## Rules

- One canonical path per concern — delete duplicates before adding code
- WSL + Windows: one stack on 8001/8002/8090
- Git: `pull --rebase origin main` then `push`
- No live funds / real DeFi until Phase 8 human approval gate