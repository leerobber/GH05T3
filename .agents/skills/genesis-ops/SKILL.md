---
name: genesis-ops
description: Operate, debug, and extend the Aethyro agent evolution pipeline — GenesisThread daemon, AethyroBridge dissent math, MutationEngine, LexGenSeal IP vault, ProprioceptionEngine, and PatentOffice. Use this skill whenever the user asks about: agent evolution, mutation, heartbeat ticks, orphan pruning, dissent scoring, spawn triggers, IP sealing, patent review queue, sensor readings (VRAM, CPU, RAM), fitness breakthroughs, genome editing, or any of the OSS core subsystems. Also triggers on "why isn't genesis running", "how does dissent work", "seal this agent", "check patents", "mutation rate", "prune orphans", "breakthrough detected", "proprioception spike", "run the genesis thread", or any reference to the 5 OSS core modules added in the binary upgrade session.
---

# Aethyro Agent Evolution Pipeline

**OSS core modules**: `C:\Users\leer4\GH05T3\backend\oss\core\`  
**Supporting module**: `C:\Users\leer4\GH05T3\backend\oss\patent_office.py`  
**Ledger integration**: all modules use `get_chronos_ledger()` — see `binary-ledger` skill for layout

---

## 1. GenesisThread — Heartbeat Daemon

**File**: `backend/oss/core/genesis_thread.py`

GenesisThread is the evolution clock. It runs as a background daemon, ticking at a configurable interval. Each tick:
1. **Prunes orphans** — agents whose heartbeat is stale (missed N+ ticks) are zeroed out and their slots freed
2. **Runs dissent pass** — AethyroBridge scores each agent against the swarm mean; breakthrough agents may spawn offspring
3. **Stamps heartbeat** — `ledger.update_heartbeat(slot, tick)` for every active agent

```python
from backend.oss.core.genesis_thread import GenesisThread

thread = GenesisThread(
    tick_interval_s=3.0,      # heartbeat cadence — 3 seconds is the default
    orphan_timeout_ticks=5,   # agent is pruned after 5 missed heartbeats (15s at default)
    breakthrough_threshold=2.0,  # dissent boost > 2.0 triggers spawn
)
thread.start()   # starts daemon thread — non-blocking

# To stop cleanly:
thread.stop()
thread.join(timeout=5)
```

### Manual tick (for testing)

```python
thread._tick_once()  # runs one full orphan-prune → dissent → heartbeat cycle
```

### Monitoring tick state

```python
print(thread.tick_count)       # number of ticks completed
print(thread.spawn_count)      # how many agents have been spawned this session
print(thread.last_prune_count) # agents pruned in the last tick
```

### Orphan pruning logic

An agent is "orphaned" when:
```
current_tick - stored_heartbeat > orphan_timeout_ticks
```
Heartbeat is stored as `tick % (2^24)`, so wrap-around is handled. When pruned, `ledger.write_zero(slot)` is called, freeing the slot for `write_at_next_available_slot()`.

---

## 2. AethyroBridge — Dissent Math

**File**: `backend/oss/core/aethyro_bridge.py`

Dissent measures how much an agent's desire vector diverges from the swarm mean. High dissent = potential breakthrough. The formula is exponential to reward outliers:

```
boost = exp(euclidean_distance × 0.15)
```

- At `distance=0.0` → `boost=1.0` (agent is average, no spawn)
- At `distance=3.5` → `boost≈1.69`
- At `distance=10.0` → `boost≈4.48`
- At `distance=∞` → `boost>>2.0` → spawn triggered

NaN protection is applied at two layers: (1) when computing the swarm mean via `desires_matrix()` (already NaN-to-zero), (2) before exponentiation via `np.nan_to_num`.

```python
from backend.oss.core.aethyro_bridge import AethyroBridge

bridge = AethyroBridge()
result = bridge.evaluate(slot=42)
# → {"slot": 42, "distance": 1.83, "boost": 1.32, "spawned": False}

# Evaluate all active agents
results = bridge.evaluate_all()
# → list of dicts, sorted by boost descending
spawned = [r for r in results if r["spawned"]]
```

### Spawn mechanics

When `boost > breakthrough_threshold`:
1. Parent's desires + Gaussian drift → child desires (via MutationEngine)
2. `ledger.write_at_next_available_slot(desires=child_desires, parent_offset=parent_slot, generation=parent_gen+1, fitness=0.5)`
3. Parent gets `SCRATCH_NEEDS_REVIEW` flag set so PatentOffice can inspect the lineage

### Tuning dissent sensitivity

The `0.15` exponent constant controls sensitivity. Higher values make breakthroughs rarer but more extreme:
- `0.10` → boost reaches 2.0 at distance≈13.8 (very permissive)
- `0.15` → boost reaches 2.0 at distance≈9.2 (default)
- `0.20` → boost reaches 2.0 at distance≈6.9 (strict)

To change it, edit `DISSENT_SCALE = 0.15` in `aethyro_bridge.py`.

---

## 3. MutationEngine — Offspring Generation

**File**: `backend/oss/core/mutation.py`

Generates child desire vectors from a parent using a Bernoulli mask (which dimensions mutate?) and Gaussian drift (how much?).

```python
from backend.oss.core.mutation import MutationEngine

engine = MutationEngine(
    mutation_rate=0.3,    # 30% of desire dimensions mutate per offspring
    drift_sigma=0.05,     # standard deviation of Gaussian drift per mutated dimension
    seed=None,            # set for reproducible mutations (testing)
)

parent_desires = (0.7, 0.5, 0.3, 0.8, 0.6, 0.4, 0.9)
child_desires  = engine.mutate(parent_desires)
# → tuple of 7 floats, each clipped to [0,1]

# Batch mutation (for population-level operations)
children = engine.mutate_batch(parent_desires, n=10)
# → list of 10 tuples
```

### Mutation diagnostics

```python
# See which dimensions changed
parent = (0.7, 0.5, 0.3, 0.8, 0.6, 0.4, 0.9)
child  = engine.mutate(parent)
dims   = ["KNOWLEDGE","SKILL","STATUS","EXPERIENCE","CREATION","CONNECTION","FREEDOM"]
for i, (p, c) in enumerate(zip(parent, child)):
    delta = c - p
    if abs(delta) > 0.001:
        print(f"  {dims[i]}: {p:.3f} → {c:.3f} (Δ{delta:+.3f})")
```

### Rate and drift tradeoffs

| mutation_rate | drift_sigma | Effect |
|---|---|---|
| 0.1 | 0.02 | Slow incremental drift — stable populations |
| 0.3 | 0.05 | Default — moderate diversity pressure |
| 0.5 | 0.10 | Fast exploration — high variance |
| 0.7 | 0.15 | Chaotic — useful only for reset/restart scenarios |

---

## 4. LexGenSeal — IP Vault

**File**: `backend/oss/core/seal.py`  
**Vault location**: `C:\Users\leer4\GH05T3\data\ip_vault\`

LexGenSeal creates an append-only SHA256-signed record for any agent that represents a patentable discovery. The vault is a flat directory of `.json` records — no database, no network, audit-ready.

```python
from backend.oss.core.seal import LexGenSeal

seal = LexGenSeal()

# Seal an agent (called automatically by PatentOffice when it approves)
record_id = seal.seal_agent(
    slot=42,
    desires=ledger.read_agent(42)["desires"],
    metadata={
        "generation": 3,
        "fitness": 0.94,
        "parent_offset": 17,
        "domains": ["KNOWLEDGE", "CREATION"],
        "reason": "breakthrough via dissent score 3.7",
    }
)
print(f"Sealed: {record_id}")  # → "seal_20260620_143022_slot042_abc123de"

# Read a seal record
record = seal.read_record(record_id)
print(record["sha256"])       # integrity hash
print(record["timestamp"])    # ISO timestamp
print(record["desires"])      # desire vector at time of sealing
print(record["valid"])        # seal.verify_record(record_id) result

# List all sealed records
records = seal.list_records()
for r in records:
    print(r["record_id"], r["slot"], r["timestamp"])

# Verify integrity of entire vault
report = seal.audit_vault()
print(f"Valid: {report['valid_count']}, Tampered: {report['invalid_count']}")
```

### When sealing happens automatically

1. PatentOffice clears an agent from review queue (`SCRATCH_NEEDS_REVIEW`) and approves it
2. PatentOffice calls `seal.seal_agent(...)` 
3. `SCRATCH_PATENTED` bit is set in the ledger scratchpad
4. The vault `.json` file is the permanent record

### Vault file format

Each file: `data/ip_vault/seal_{timestamp}_{slot}_{hash8}.json`
```json
{
  "record_id": "seal_20260620_143022_slot042_abc123de",
  "slot": 42,
  "desires": {"KNOWLEDGE": 0.87, "SKILL": 0.45, ...},
  "metadata": {"generation": 3, ...},
  "timestamp": "2026-06-20T14:30:22.841Z",
  "sha256": "a3f9c12d..."
}
```

---

## 5. ProprioceptionEngine — Hardware Sensing

**File**: `backend/oss/core/proprioception.py`

Read-only sensor that reports system resources via `pynvml` (GPU) and `psutil` (CPU/RAM). Never modifies anything — pure sensing layer.

```python
from backend.oss.core.proprioception import ProprioceptionEngine

engine = ProprioceptionEngine()
reading = engine.read()
# → {
#      "vram_used_mb": 4096, "vram_total_mb": 8192, "vram_pct": 50.0,
#      "gpu_util_pct": 72.0,
#      "ram_used_gb": 9.1, "ram_total_gb": 16.0, "ram_pct": 56.9,
#      "cpu_pct": 24.3,
#      "timestamp": 1750432222.0,
#      "gpu_available": True
#   }

# Signals (derived interpretations of raw readings)
signals = engine.signals(reading)
# → list of signal dicts, empty if no thresholds exceeded

# Example signals:
# [{"type": "VRAMShunt",      "severity": "warning", "detail": "VRAM at 85%"}]
# [{"type": "GenomicSpike",   "severity": "info",    "detail": "CPU at 94%"}]
# [{"type": "LexGenSealSignal","severity":"info",    "detail": "RAM pressure 91%"}]
```

### Signal types and thresholds

| Signal | Condition | Meaning |
|---|---|---|
| `VRAMShunt` | vram_pct > 80% | Ollama under pressure — GenesisThread should slow tick rate |
| `GenomicSpike` | cpu_pct > 90% | Mutation/dissent pass is CPU-saturating — reduce batch size |
| `LexGenSealSignal` | ram_pct > 88% | Seal vault write may be slow — delay non-critical sealing |

### Integration with GenesisThread

```python
# GenesisThread checks signals before each tick
reading = engine.read()
signals = engine.signals(reading)
for sig in signals:
    if sig["type"] == "VRAMShunt":
        time.sleep(5)   # back off before next tick
        break
```

---

## 6. PatentOffice — Review Queue Processor

**File**: `backend/oss/patent_office.py` (not in core/, but integrates all core modules)

PatentOffice processes the review queue: agents with `SCRATCH_NEEDS_REVIEW` set. It infers domain keywords from the desire vector, decides whether to approve or reject, and either seals approved agents or clears rejected ones.

```python
from backend.oss.patent_office import PatentOffice
from backend.oss.core.seal import LexGenSeal

office = PatentOffice(seal=LexGenSeal())

# Process all pending review items
report = office.process_queue()
print(f"Approved: {report['approved']}, Rejected: {report['rejected']}")

# Review a single slot manually
decision = office.review_slot(slot=42)
print(decision)
# → {"slot": 42, "approved": True, "domains": ["KNOWLEDGE", "CREATION"], "reason": "high fitness + novel domain combo"}

# See what's in the queue
queue = office.get_review_queue()  # returns list of slot indices with SCRATCH_NEEDS_REVIEW
print(f"{len(queue)} agents pending review: {queue}")
```

### Approval criteria (domain-agnostic)

PatentOffice doesn't know about CPAs or AI — it's domain-agnostic. It approves based on:
1. Fitness above threshold (default: 0.7)
2. At least 2 desire dimensions significantly elevated (> 0.65)
3. Generation ≥ 2 (has gone through at least one mutation cycle)

Keyword inference maps high-desire dimensions to domain terms:
- `KNOWLEDGE+CREATION` → `["analytical_reasoning", "generative_capacity"]`
- `SKILL+STATUS` → `["domain_expertise", "authority"]`
- etc.

These keywords appear in the vault record metadata — they're for human readability, not machine processing.

---

## Full Pipeline: How It All Connects

```
GenesisThread (ticks every 3s)
  │
  ├─ ProprioceptionEngine.read() → signals → throttle if VRAMShunt
  │
  ├─ Orphan prune pass
  │   └─ ledger.update_heartbeat(stale_slot) missed → ledger.write_zero(slot)
  │
  ├─ AethyroBridge.evaluate_all()
  │   └─ for each agent: compute dissent boost = exp(dist × 0.15)
  │   └─ if boost > 2.0:
  │       MutationEngine.mutate(parent_desires) → child_desires
  │       ledger.write_at_next_available_slot(child)
  │       ledger.set_scratch_bit(parent, SCRATCH_NEEDS_REVIEW)
  │
  └─ PatentOffice.process_queue()  (every N ticks, not every tick)
      └─ for each SCRATCH_NEEDS_REVIEW slot:
          if approved:
            LexGenSeal.seal_agent(slot, desires, metadata)
            ledger.set_scratch_bit(slot, SCRATCH_PATENTED)
          ledger.clear_scratch_bit(slot, SCRATCH_NEEDS_REVIEW)
```

---

## Common Diagnostics

### Why is genesis not evolving anything?

```python
ledger = get_chronos_ledger()
stats = ledger.stats()
print(f"Active agents: {stats['active_slots']}")
print(f"Mean fitness: {stats['mean_fitness']:.3f}")

# Check if any agents have high enough fitness to diverge
fv = ledger.fitness_vector()
print(f"Agents with fitness > 0.7: {(fv > 0.7).sum()}")

# Check current swarm mean desires
dm = ledger.desires_matrix()
print("Swarm mean desires:", dm.mean(axis=0))
```

If mean fitness < 0.3 or all agents cluster near mean desires → little dissent → no spawns. Inject diverse seed agents to break symmetry.

### How to inject a diverse seed population

```python
import random
ledger = get_chronos_ledger()
for _ in range(20):
    desires = tuple(random.random() for _ in range(7))
    ledger.write_at_next_available_slot(
        desires=desires,
        maturity=1,
        fitness=random.uniform(0.5, 0.9),
        scratchpad=0,
    )
```

### Patent queue stuck?

```python
from backend.oss.patent_office import PatentOffice
from backend.oss.core.seal import LexGenSeal
from backend.oss.core.chronos_ledger import SCRATCH_NEEDS_REVIEW, get_chronos_ledger

ledger = get_chronos_ledger()
queue = ledger.find_by_scratch_bit(SCRATCH_NEEDS_REVIEW)
print(f"{len(queue)} agents pending review")
for slot in queue[:5]:
    agent = ledger.read_agent(int(slot))
    print(f"  slot {slot}: fitness={agent['fitness']:.3f} gen={agent['generation']}")
```

### Check sealed patents

```python
from backend.oss.core.seal import LexGenSeal
seal = LexGenSeal()
records = seal.list_records()
print(f"{len(records)} sealed patents in vault")
audit = seal.audit_vault()
print(f"Integrity: {audit['valid_count']} valid, {audit['invalid_count']} tampered")
```
