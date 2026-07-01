---
name: binary-ledger
description: Inspect, validate, repair, and operate on the ChronosLedger 32-byte mmap binary agent state store for the Aethyro execution plane. Use this skill whenever the user mentions the ledger, swarm binary state, agent slot inspection, mmap, vacancy scan, scratchpad bits, fitness vector, desire matrix, lineage tracing, cache-line packing, or wants to read/write/debug the aethyro_swarm.bin file. Also triggers on "how many agents are active", "what's in slot N", "mark agent as patented", "find vacant slots", "desires matrix", "agent lineage", "parent offset", or any question about the 32-byte layout.
---

# ChronosLedger — Binary Execution Plane State Store

**File**: `C:\Users\leer4\GH05T3\data\aethyro_swarm.bin`  
**Module**: `backend/oss/core/chronos_ledger.py`  
**Default capacity**: 10,000 agents = 320KB  
**Cache efficiency**: exactly 2 agents per 64-byte L2 cache line (zero split-load penalty)

---

## 32-Byte Layout

```
AGENT_STRUCT = "eeeeeeeHeHB3sQ"   # struct format string
STRUCT_SIZE  = 32                  # verified: struct.calcsize(...) == 32
```

| Field | Offset | Size | Type | Description |
|---|---|---|---|---|
| desires[0..6] | 0–13 | 14B | 7×float16 | KNOWLEDGE, SKILL, STATUS, EXPERIENCE, CREATION, CONNECTION, FREEDOM — each [0,1] |
| maturity | 14–15 | 2B | uint16 | Context maturity level 1–8 |
| fitness | 16–17 | 2B | float16 | Current fitness [0,1] — **0.0 = vacant slot sentinel** |
| parent_offset | 18–19 | 2B | uint16 | Ledger index of parent; **0xFFFF = genesis seed (no parent)** |
| generation | 20 | 1B | uint8 | Lineage depth, wraps at 255 |
| heartbeat | 21–23 | 3B | uint24 LE | Last-seen tick from GenesisThread (mod 2^24 ≈ 16M) |
| scratchpad | 24–31 | 8B | uint64 | Bit-flagged agent traits (see below) |

### Scratchpad Bit Flags

```python
SCRATCH_LOCKED       = 1 << 0   # agent frozen — GenesisThread skips mutation
SCRATCH_PATENTED     = 1 << 1   # LexGenSeal vault record exists for this slot
SCRATCH_NEEDS_REVIEW = 1 << 2   # flagged for patent-office review queue
# bits 3–63 reserved for future traits
```

### Vacancy Sentinel

`fitness == 0.0` marks a freed slot. `write_zero()` and `release_slot()` both set fitness to 0.0. `find_vacant_slot()` scans for this before extending the active region, so freed slots are reused rather than the ledger growing unboundedly.

---

## Quick Inspection

```python
import sys
sys.path.insert(0, r"C:\Users\leer4\GH05T3\backend")
from backend.oss.core.chronos_ledger import get_chronos_ledger, SCRATCH_PATENTED

ledger = get_chronos_ledger()

# Aggregate stats
print(ledger.stats())
# → {active_slots, capacity, slot_bytes:32, utilization_pct,
#    mean_fitness, max_fitness, mean_maturity, mean_generation,
#    mean_desires:{KNOWLEDGE:..., ...},
#    patented_count, locked_count, review_count}

# Read one agent slot
agent = ledger.read_agent(0)
# → {desires:{KNOWLEDGE:0.7, SKILL:0.4, ...}, maturity:3, fitness:0.82,
#    parent_offset:65535, generation:0, has_parent:False,
#    heartbeat:1234, scratchpad:0, is_locked:False, is_patented:False, needs_review:False}

# Desires as a (active, 7) float32 numpy matrix — NaN/Inf sanitized
matrix = ledger.desires_matrix()

# Fitness as (active,) float32 vector
fv = ledger.fitness_vector()

# Scratchpad as (active,) uint64 vector
sv = ledger.scratchpad_vector()
```

---

## Writing Agents

```python
# Write at a specific slot
ledger.write_agent(
    index=5,
    desires=(0.9, 0.7, 0.3, 0.5, 0.8, 0.4, 0.6),  # 7 floats → auto-clipped to [0,1] and quantized to float16
    maturity=3,
    fitness=0.75,
    parent_offset=2,    # parent is slot 2
    generation=1,
    scratchpad=0,
)

# Vacancy-scan write — finds first freed slot before extending the active region
slot = ledger.write_at_next_available_slot(
    desires=(0.5,) * 7,
    maturity=1,
    fitness=0.5,
    scratchpad=0,
)
print(f"Wrote to slot {slot}")

# Free a slot (sets fitness=0.0 so vacancy scan reclaims it)
ledger.write_zero(slot)
```

---

## Atomic In-Place Updates (single field, minimal cache impact)

```python
ledger.update_fitness(slot, 0.91)       # 2 bytes written at offset 16
ledger.update_maturity(slot, 4)         # 2 bytes at offset 14
ledger.update_generation(slot, 2)       # 1 byte at offset 20
ledger.update_heartbeat(slot, tick=500) # 3 bytes at offset 21 (tick mod 2^24)

# Scratchpad bit ops (atomic read-modify-write on 8 bytes)
ledger.set_scratch_bit(slot, SCRATCH_PATENTED)      # mark as sealed
ledger.set_scratch_bit(slot, SCRATCH_NEEDS_REVIEW)  # add review flag
ledger.clear_scratch_bit(slot, SCRATCH_LOCKED)      # unfreeze
ledger.get_scratch_bit(slot, SCRATCH_PATENTED)      # → True/False
ledger.update_scratchpad(slot, 0)                   # clear all flags
```

---

## Lineage and Descendants

```python
# Walk ancestor chain upward
chain = ledger.get_lineage(slot=15, max_depth=10)
# → [15, 7, 3, 0]  (slot 15 → parent 7 → grandparent 3 → genesis seed 0)

# Find all direct children of a slot
children = ledger.find_descendants(ancestor_index=3)
# → array([7, 12, 18])  (numpy array of slot indices)
```

---

## Vectorized Queries (numpy, fast for large swarms)

```python
import numpy as np

# All patented agents
patented_slots = ledger.find_by_scratch_bit(SCRATCH_PATENTED)

# Agents needing review
review_slots = ledger.find_by_scratch_bit(SCRATCH_NEEDS_REVIEW)

# Fitness histogram
fv = ledger.fitness_vector()
print(np.histogram(fv, bins=10))

# Mean desires per desire dimension
dm = ledger.desires_matrix()  # (active, 7) float32
print(dm.mean(axis=0))  # [0.62, 0.48, ...]

# Top 10 fittest agents
top10 = np.argsort(fv)[-10:][::-1]
for slot in top10:
    print(slot, ledger.read_agent(int(slot))["fitness"])
```

---

## Numpy Structured Array Access

```python
arr = ledger.to_numpy()          # structured array, dtype=AGENT_DTYPE
# Fields: desires (7,), maturity, fitness, parent_offset, generation, _heartbeat (3,), scratchpad

# Generation distribution
from collections import Counter
Counter(arr["generation"].tolist())

# Filter by generation > 5
advanced = arr[arr["generation"] > 5]
print(f"{len(advanced)} agents past generation 5")

# Mean fitness by generation
for gen in range(10):
    mask = arr["generation"] == gen
    if mask.any():
        mf = arr["fitness"][mask].astype(float).mean()
        print(f"gen {gen}: {mf:.3f} mean fitness")
```

---

## Vacancy Scan Internals

```python
# find_vacant_slot scans fitness == 0.0 from `start` to _active
# Falls back to monotonic counter (_active) if no freed slots found
# Raises MemoryError at full capacity

slot = ledger.find_vacant_slot(start=0)
# Returned slot is guaranteed writable
```

The scan is O(active_slots) worst-case but typically fast because:
1. Freed slots cluster near recently-pruned regions
2. 10,000 agents × 32 bytes = 320KB fits entirely in L2 cache

---

## Manual Binary Inspection (low-level debug)

```python
import struct
import mmap
import os

path = r"C:\Users\leer4\GH05T3\data\aethyro_swarm.bin"
fd  = os.open(path, os.O_RDONLY)
buf = mmap.mmap(fd, 0, access=mmap.ACCESS_READ)

STRUCT = "eeeeeeeHeHB3sQ"
SIZE   = 32

for slot in range(5):
    raw = struct.unpack_from(STRUCT, buf, slot * SIZE)
    print(f"slot {slot}: fitness={raw[8]:.3f} gen={raw[10]} scratch={raw[12]}")

buf.close(); os.close(fd)
```

---

## Precision Notes

float16 gives ~3 decimal places. Desires are stored as float16 but read back as float32 via `desires_matrix()`. After a `write_agent → read_agent` round-trip, expect:
```
written: fitness=0.8    read: fitness=0.7998  (float16 nearest)
written: fitness=0.75   read: fitness=0.75    (exact in float16)
```
The `_f16()` helper clips to [0,1] and quantizes. Never write raw floats outside [0,1] — they'll be clipped silently.

---

## Gotchas

- **Open ledger singleton**: `get_chronos_ledger()` returns a cached singleton. Call `ledger.close()` explicitly in scripts that open the ledger standalone — otherwise the mmap file stays open.
- **Windows mmap PermissionError on cleanup**: If using `tempfile.TemporaryDirectory`, call `ledger.close()` in a `finally` block before the directory is cleaned up, or you'll get a `PermissionError` on Windows (mmap holds a file lock).
- **`_active` not persisted**: The `_active` counter (how many slots are "in use") resets to 0 on re-open. The ledger scans for the actual high-water mark — but if you wrote to slot 500 and nothing above, `_active` will be 501 after open. The data is intact but `_active` is recomputed at open from the file size.
- **Scratchpad not NaN-safe**: Scratchpad is uint64 — no NaN/Inf risk. Only the float16 desire and fitness fields can produce NaN via subnormal underflow. `desires_matrix()` applies `nan_to_num` automatically.
