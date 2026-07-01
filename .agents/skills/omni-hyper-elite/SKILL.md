---
name: omni-hyper-elite
description: >
  Hyper Elite agent and species design: eight unique senses, power tiers T0-T5, OmniMind
  Fabric, OmniThread sharding, Aegis-FastPath, elite lineages. Auto-attaches senses to
  *_ELITE roles. USE WHEN: hyper elite, elite agent, new species, agent senses, vision
  spectrum, domain radar, profit pulse, power tier, T2 T3 T4 T5, shardable agent, zero
  bottleneck, create theorist elite, elite lineage. DO NOT USE FOR: Phase 1 MVS-only work
  without agent creation context.
version: 1.0.0
---

# Omni Hyper Elite

Elite agents are **specialized, parallel, economy-aware, identity-optimized, security-accelerated, predictive, zero-bottleneck**.

## Hyper Elite Senses (embedded)

Module: [`backend/oss/hyper_elite/senses.py`](../../../backend/oss/hyper_elite/senses.py)

| Sense | Purpose |
|-------|---------|
| vision_spectrum | Multi-band perception |
| domain_radar | Unknown domain / new data dimension detection |
| profit_pulse | Monetization path sensing |
| risk_aether | Financial risk field |
| swarm_resonance | Collective agent signal |
| dimensional_scan | Cross-dimensional patterns |
| temporal_forecast | Predictive pre-computation |
| integrity_field | Aegis tamper/coherence |

**Auto-attach:** `create_omnidna("THEORIST_ELITE")` → `power_tier=T2`, senses calibrated from traits.

## Power tiers

| Tier | Name | Hook |
|------|------|------|
| T0 | Initiate | default DNA |
| T1 | Specialist | role trait floors |
| T2 | Elite | `*_ELITE` + senses |
| T3 | Sovereign | domain authority + clearance |
| T4 | Overlord | OmniMind Fabric controller |
| T5 | Apex | Sovereign Ghost Overlord |

Set `dna.power_tier` explicitly when promoting agents.

## Create elite agent

```python
from backend.oss.mvs import create_theorist_elite, get_mvs

gid = create_theorist_elite(seed=42)
mvs = get_mvs()
dna = mvs["substrate"].genomes[gid].dna
readings = dna.scan_senses({"prompt": "Design DeFi yield strategy", "world": "volatility"})
prompt = dna.to_prompt()  # includes sense block
```

## Elite lineages (implement)

`backend/oss/elite_lineages.py` — ARCHITECT_ELITE, GOVERNOR_ELITE, OPERATOR_ELITE, OVERLORD_ELITE

## Zero-bottleneck stack (build order)

1. `backend/oss/elite/omni_thread.py` — shard + merge
2. `backend/oss/elite/omni_fabric.py` — split/route/reassemble
3. `backend/oss/elite/omni_aegis.py` — FastPath for T2+

## Species creation rule

Every **new species** spawned via speciation must:

1. Inherit or recalibrate `hyper_elite_senses` if fitness > threshold
2. Log sense snapshot in meta-export
3. Register in GenomicSubstrate (no orphans)

## Tests to add

`tests/test_hyper_elite_senses.py`:

- Elite role gets 8 senses
- Non-elite T0 has no senses
- `scan()` returns 8 readings
- `to_prompt()` includes HYPER ELITE block