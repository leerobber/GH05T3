---
name: bme
description: >
  Binary Multiverse Engine (BME) — zero-latency evolutionary substrate for GH05T3.
  Use this skill whenever working with multi-universe agent evolution, skill genomes,
  role tier promotion, universe migration, speciation events, the SkillRegistry binary
  file, GenomePlane mmap, or the BMEBridge integration layer.
---

# Binary Multiverse Engine (BME)

Zero-latency evolutionary substrate. No LLM calls. No JSON. No DB. Pure binary mmap
dereferences and numpy array ops. All operations are O(1) or O(N) over pre-compiled
binary files.

## File Map

```
backend/oss/core/
  skill_registry.py     ← SkillRegistry: skills.bin binary DNA library
  genome_plane.py       ← GenomePlane: genome_plane.bin per-agent skill genomes
  universe_engine.py    ← UniverseEngine: desire amplification, migration, promotion
  bme_bridge.py         ← BMEBridge: cross-universe integration hub
  chronos_ledger.py     ← ChronosLedger: existing 32-byte agent state (BME-extended)
  mutation.py           ← MutationEngine: desire vector evolution (BME-extended)
  genesis_thread.py     ← GenesisThread: tick loop (BME Phase 4 added)

data/
  skills.bin            ← compiled skill registry (auto-created on first import)
  genome_plane.bin      ← per-agent skill genomes (auto-created)
  aethyro_swarm.bin     ← ChronosLedger (existing)
```

---

## Binary Layouts

### skills.bin (SkillRegistry)

```
FILE HEADER   32 bytes     magic=0x424D4531 ("BME1"), version, num_universes, total_skills
UNIVERSE DIR  128 bytes    8 × 16-byte entries: universe_id, name, skill_offset_idx, skill_count
SKILL RECORDS N × 64 bytes  one record per skill (cache-line aligned)
```

Skill record (64 bytes, `SKILL_STRUCT = "<I20sQQB3sffQBBH"`):
```
skill_id        uint32   4   universe*10000 + local_id
name            char[20] 20  null-padded ASCII
input_sig       uint64   8   bitmask of accepted IO types
output_sig      uint64   8   bitmask of produced IO types
dominance       uint8    1   0=recessive 1=additive 2=dominant 3=co-dominant
_pad            3s       3
mutation_rate   float32  4   per-gene mutation probability [0,1]
reward_weight   float32  4   fitness contribution [0,1]
universe_bits   uint64   8   universe-specific encoded state
flags           uint8    1   bit0=elite_only bit1=experimental bit2=governance_locked
role_tier       uint8    1   minimum tier to access
discovery_count uint16   2   usage counter
```

O(1) lookup: `SkillRegistry.get_skill(skill_id)` → dict via pre-built `_index` dict.

### genome_plane.bin (GenomePlane)

```
SLOT 0    [64 bytes]  8 genes × 8 bytes
SLOT 1    [64 bytes]
...indexed by same slot as ChronosLedger
```

Gene record (8 bytes, `GENE_STRUCT = "<BBHeB1s"`):
```
universe_id  uint8   1   which universe (0-7)
role_tier    uint8   1   tier required to express
skill_id     uint16  2   index into SkillRegistry
expression   float16 2   activation weight [0.0–1.0]
flags        uint8   1   bit0=active bit1=dominant bit2=mutated bit3=inherited
reserved     1s      1
```

### ChronosLedger scratchpad extension (bits 3-12)

```
bit 0     SCRATCH_LOCKED         agent frozen
bit 1     SCRATCH_PATENTED       LexGenSeal record exists
bit 2     SCRATCH_NEEDS_REVIEW   flagged for review
bits 3-5  SCRATCH_UNIVERSE_MASK  universe ID 0-7  (UNIVERSE_SHIFT=3)
bits 6-8  SCRATCH_ROLE_TIER_MASK role tier 0-7    (ROLE_TIER_SHIFT=6)
bit 9     SCRATCH_MIGRANT        migrated this gen
bit 10    SCRATCH_SPECIATION     triggered speciation
bit 11    SCRATCH_ELITE_PROPOSAL proposed new skill
bit 12    SCRATCH_BREAKTHROUGH_GENE genome contrib >= 0.80
bits 13-63 reserved
```

---

## Universes (7+1)

| ID | Name       | Top desires amplified          | Mutation rate | Adjacency           |
|----|------------|--------------------------------|---------------|---------------------|
| 0  | Physics    | KNOWLEDGE×2.5 CREATION×1.8    | 0.02          | Chemistry Cosmic Entropy |
| 1  | Chemistry  | CREATION×2.2 KNOWLEDGE×2.0    | 0.04          | Physics Biology Entropy |
| 2  | Biology    | SURVIVAL×2.0 CONNECTION×1.8   | 0.06          | Chemistry Fungal Psychology |
| 3  | Psychology | CONNECTION×2.5 STATUS×2.0     | 0.05          | Biology Fungal Cosmic |
| 4  | Fungal     | CONNECTION×3.0 FREEDOM×2.0    | 0.08          | Biology Psychology Entropy |
| 5  | Cosmic     | FREEDOM×2.5 KNOWLEDGE×2.0     | 0.03          | Physics Psychology Entropy |
| 6  | Entropy    | CREATION×2.0 FREEDOM×2.2      | 0.20          | Physics Chemistry Fungal Cosmic |
| 7  | Hybrid     | ALL×2.0                        | 0.03          | all (requires tier≥5) |

Fitness formula: `base_fitness × (0.5 + 0.5 × dot(desires_norm, amp) / max_amp)`

---

## Role Tier Ladder

| Tier | Name                        | min_fitness | min_gen | min_disc |
|------|-----------------------------|-------------|---------|----------|
| 0    | Base                        | —           | —       | —        |
| 1    | Specialist                  | 0.30        | 3       | 0        |
| 2    | Elite                       | 0.50        | 8       | 2        |
| 3    | Apex Synthesist             | 0.65        | 15      | 4        |
| 4    | Quantum Architect (domain)  | 0.75        | 25      | 6        |
| 5    | String Theorist (frontier)  | 0.85        | 40      | 8        |
| 6    | Meta-Genomic Governor       | 0.92        | 60      | 10       |
| 7    | Substrate Philosopher       | 0.97        | 90      | 12       |
| 8-15 | 2026 Frontier roles         | genome-defined                 |

2026 frontier roles (tier 8+): Dimensional Weaver, Emergence Catalyst, Causal Weaver,
Resonance Architect, Attention Alchemist, Frontier Economist, Entropy Sovereign, Data God.
Classified by skill-genome composition, not scratchpad bits.

Speciation gate: tier >= 4 allows `BMEBridge.speciation_event()` (propose new skill to registry).

---

## Seed Skill Library

39 initial skills compiled into `skills.bin` at startup:
- Physics: QuantumEntangle, StringVibration, WaveCollapse, TopologyShift, EnergyQuantize
- Chemistry: CatalystReact, MolecularBond, Polymerize, DissolveBarrier, EnzymaticCleave
- Biology: MycelialNetwork, SymbioticLink, AdaptiveGrowth, SporeRelease, NecrosisSignal
- Psychology: AttentionTrigger, EmotionalResonance, PersuasionMolecule, CognitiveBias, StatusSignaling
- Fungal: HyphalExtension, ResourceCapture, NetworkResilience, DigestionField, FruitingBody
- Cosmic: GravityWell, TimeDilation, HorizonCrossing, EntropicShield, DarkMatterDense
- Entropy: ChaosInjection, StochResonance, DecayResistance, BifurcationPoint, DissipativeStruct
- Hybrid: QuantumCatalysis, ChemoBioFusion, PsychoPhysResonance, FungalEntropyWeb, UniverseFounder

---

## API Quick Reference

### SkillRegistry
```python
from backend.oss.core.skill_registry import get_skill_registry
reg = get_skill_registry()

reg.get_skill(skill_id)                          # O(1) → dict or None
reg.get_skill_by_universe(universe_id, local_id) # O(1) → dict or None
reg.get_universe_skills(universe_id)             # → List[dict]
reg.get_accessible_skills(universe_id, role_tier)# → List[dict] (filtered by tier + governance)
reg.propose_skill(universe_id, name, input_sig, output_sig, ...) # → new skill_id
reg.stats()                                      # → per-universe summary dict
```

### GenomePlane
```python
from backend.oss.core.genome_plane import get_genome_plane
genome = get_genome_plane()

genome.read_gene(slot, gene_idx)      # → dict or None
genome.read_genome(slot)              # → List[dict | None] (8 items)
genome.active_genes(slot)             # → List[dict] (expression > 0)
genome.expressed_skill_ids(slot)      # → List[int] sorted by expression desc
genome.write_gene(slot, gene_idx, universe_id, role_tier, skill_id, expression, flags)
genome.crossover(parent_a, parent_b, child_slot)
genome.inject_gene(slot, universe_id, role_tier, skill_id, expression=0.5) # → gene_idx
genome.mutate_genome(slot, mutation_rate=0.05, expression_drift=0.1) # → mutated_count
genome.expression_vector(slot)        # → float16 ndarray (8,) — zero alloc fast path
genome.genome_fitness_contribution(slot)  # → float (weighted sum of expressions)
```

### UniverseEngine
```python
from backend.oss.core.universe_engine import get_universe_engine
eng = get_universe_engine()

eng.amplified_fitness(universe_id, desires_f32, base_fitness) # → float
eng.compare_universe_fitness(desires_f32, base_fitness)       # → Dict[uid, float]
eng.migration_candidate(current_universe, desires, base_fitness, delta_gate=0.15)
eng.promotion_criteria(current_tier, fitness, generation, discovery_count) # → bool
eng.universe_mutation_vector(universe_id, desires, rng)       # → float16 ndarray (7,)
```

### BMEBridge
```python
from backend.oss.core.bme_bridge import get_bme_bridge
bme = get_bme_bridge()

# Scratchpad read/write
bme.get_agent_universe(slot)              # → int 0-7
bme.set_agent_universe(slot, universe_id)
bme.get_role_tier(slot)                  # → int 0-7
bme.set_role_tier(slot, tier)

# Evolution
bme.check_migration(slot)                # → target_uid or None
bme.migrate_agent(slot, target_universe) # → bool
bme.check_promotion(slot)                # → bool (promotes in place)
bme.check_breakthrough_gene(slot)        # → bool (sets BREAKTHROUGH_GENE bit)
bme.speciation_event(slot, skill_name, input_sig, output_sig) # → skill_id or None (tier gate)
bme.inherit_genome(parent_slot, child_slot)  # called by GenesisThread on spawn

# Tick (called by GenesisThread)
bme.universe_pass(active_slots)          # → Dict[migrations, promotions, breakthroughs, ...]

# SovereignCore push (async, non-blocking)
await bme.push_to_sovereign_core(universe_counts, migrations, promotions, tick)
```

### MutationEngine (extended)
```python
from backend.oss.core.mutation import get_mutation_engine
mut = get_mutation_engine()

mut.spawn_offspring_for_universe(parent_desires, universe_id, count=5)
mut.crossover_genomes(parent_a_desires, parent_b_desires, universe_id, count=2)
```

### ChronosLedger (extended)
```python
ledger.get_scratchpad(slot)            # → int (uint64)
ledger.set_scratchpad(slot, value)
ledger.get_desires(slot)               # → float16 ndarray (7,)
ledger.get_fitness(slot)               # → float
ledger.get_generation(slot)            # → int
ledger.get_universe(slot)              # → int (bits 3-5 of scratchpad)
ledger.set_universe(slot, universe_id)
ledger.get_role_tier(slot)             # → int (bits 6-8 of scratchpad)
ledger.set_role_tier(slot, tier)
```

---

## GenesisThread Tick Sequence (updated)

```
Phase 1: _prune_orphans()    — reclaim stale ledger slots
Phase 2: _dissent_pass()     — population mean → fitness boost → spawn offspring
          └→ _spawn_offspring() now:
               - inherits parent's UNIVERSE bits into child scratchpad
               - calls bme_bridge.inherit_genome(parent_slot, child_slot)
Phase 3: _breakthrough_check() — M_NOVELTY → LEX-GEN signal
Phase 4: _universe_pass()    ← NEW (BME)
               - bme_bridge.universe_pass(active_slots)
               - migration pressure, role promotions, breakthrough gene flags
               - every 10 ticks: async push to SovereignCore :9000
```

---

## Initialization Order

On process startup (no special init call needed — lazy singletons):

1. First call to `get_skill_registry()` → checks `data/skills.bin`, builds from SEED_SKILLS if absent
2. First call to `get_genome_plane()` → creates `data/genome_plane.bin` if absent (4096 slots × 64 bytes)
3. First call to `get_universe_engine()` → pure in-memory constants, instant
4. First call to `get_bme_bridge(ledger)` → wires all three above + PatentOffice

---

## Debugging

```python
# Print skill registry summary
from backend.oss.core.skill_registry import get_skill_registry
import json; print(json.dumps(get_skill_registry().stats(), indent=2))

# Inspect agent genome
from backend.oss.core.genome_plane import get_genome_plane
from backend.oss.core.skill_registry import get_skill_registry
reg, genome = get_skill_registry(), get_genome_plane()
for gene in genome.active_genes(slot=42):
    skill = reg.get_skill(gene['skill_id'])
    print(f"  [{gene['expression']:.2f}] {skill['name'] if skill else 'UNKNOWN'} (u={gene['universe_id']})")

# Check universe distribution across population
from backend.oss.core.bme_bridge import get_bme_bridge
active_slots = list(range(1000))  # adjust to actual
bme = get_bme_bridge()
print(bme.population_universe_distribution(active_slots))
print(bme.population_tier_distribution(active_slots))
```

---

## Gotchas

- `skills.bin` is append-only — `propose_skill()` closes/reopens the mmap briefly; no reads are lost
- `genome_plane.bin` auto-extends when a slot > current file is written
- `SCRATCH_UNIVERSE_MASK` occupies bits 3-5; reading raw scratchpad and checking == universe_id WILL NOT WORK — use `(scratch & SCRATCH_UNIVERSE_MASK) >> UNIVERSE_SHIFT`
- Hybrid universe (ID=7) requires `agent_tier >= 5` for migration; enforced in `UniverseEngine.migration_candidate()`
- Desire dimension ordering in `DESIRE_AMPLIFICATION` follows `universe_engine.DESIRE_NAMES` = [SURVIVAL, KNOWLEDGE, CREATION, CONNECTION, INFLUENCE, FREEDOM, STATUS] — different from `chronos_ledger.DESIRE_NAMES` = [KNOWLEDGE, SKILL, STATUS, EXPERIENCE, CREATION, CONNECTION, FREEDOM]; when bridging, use numpy index ops not name lookup
- `genome_fitness_contribution()` is a proxy for genome activation, NOT the agent's `fitness` field in ChronosLedger
