---
name: omni-brain-checkpoint
description: >
  Omni Brain checkpoint system for the Omni-Sentient build. Reads and updates resume state,
  build log, and metrics so any agent continues exactly where the last session stopped.
  USE WHEN: checkpoint, resume build, where did we leave off, continue omni build, brain
  state, last checkpoint, build progress, /omni-resume. DO NOT USE FOR: Aethyro Memory Cortex
  or unrelated project memory.
version: 1.0.0
---

# Omni Brain Checkpoint

The brain lives at **`.omni-brain/`** in the GH05T3 repo root.

## Files

| File | Role |
|------|------|
| `CHECKPOINT.json` | Machine state: phase, next_action, gates, metrics |
| `STATE.md` | Human "continue here" summary |
| `index.md` | Brain TOC |
| `topics/build-log.md` | Episodic log |
| `topics/hyper-elite-senses.md` | Sense architecture decisions |
| `topics/financial-sector-vision.md` | Monetization / DeFi mandate |

## Read checkpoint

```bash
cd /mnt/c/Users/leer4/GH05T3
python scripts/omni_brain_checkpoint.py
```

## Update after completing work

```bash
python scripts/omni_brain_checkpoint.py \
  --complete P1-W1-001 \
  --next "Migrate genomic_substrate off traits.py" \
  --next-id P1-W1-002
```

## Set metrics

```bash
python scripts/omni_brain_checkpoint.py --metric hyper_elite_senses_module=true
python scripts/omni_brain_checkpoint.py --metric theory_lab_1000_cycles=passed
```

## Advance phase (only when gate passed)

```bash
python scripts/omni_brain_checkpoint.py --set-phase 2 --week 3
```

## Agent workflow

1. Print `next_action` and `next_action_id` from CHECKPOINT.json
2. Implement exactly that item from Master Checklist in build plan
3. Run relevant tests
4. Update checkpoint + build-log
5. Report: phase, completed ID, next ID

## Checkpoint ID convention

`P{phase}-W{week}-{seq}` — e.g. `P1-W1-001`, `P8-W1-003`