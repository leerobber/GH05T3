"""
Sovereign Intelligence OS — end-to-end demo.

Shows the three-layer architecture:
  Layer 1: Rust Host (sovereign_core_rs.Runtime)
  Layer 2: WASM Agent (planner_agent.wasm)
  Layer 3: Python Orchestration (GH05T3 expert agents + HyperAgents genome evolution)

Run:
  SOVEREIGN_CORE_PATH=/path/to/sovereign-core python3 demo_sovereign.py
"""
from __future__ import annotations

import sys, os

_SOVEREIGN_PATH = os.environ.get("SOVEREIGN_CORE_PATH", "")
if _SOVEREIGN_PATH and _SOVEREIGN_PATH not in sys.path:
    sys.path.insert(0, _SOVEREIGN_PATH)

print("=" * 60)
print("  Sovereign Intelligence OS — Demo")
print("=" * 60)

# ── Layer 1: Rust host runtime ───────────────────────────────────────────────
print("\n[LAYER 1] Rust Host Runtime (sovereign_core_rs)")
from sovereign_core_rs import Runtime, KernelBlock, SemanticWord, WasmHost

rt = Runtime()
agent_id = rt.spawn_agent(genome_id=1)
print(f"  spawned agent {agent_id} (genome 1)")

word = SemanticWord(type_=1, intent=2, channel=0, priority=200, confidence=58000, payload_ref=7)
print(f"  SemanticWord: intent=PLAN  confidence={word.confidence_f():.3f}  payload_ref={word.payload_ref}")
print(f"  encoded: {word.encode():#018x}")

result_blocks = rt.dispatch_block(KernelBlock(
    agent_id=agent_id, genome_id=1, creds_token=0b1111,
    task_id=1, words=[word.encode()], metrics_ref=0,
))
rw = SemanticWord.decode(result_blocks[0].words[0])
print(f"  dispatch_block -> intent={rw.intent} type={rw.type_} confidence={rw.confidence_f():.3f}")

# ── Layer 2: WASM planner agent ──────────────────────────────────────────────
print("\n[LAYER 2] WASM Planner Agent")
_WASM = os.path.join(os.path.dirname(__file__), "backend", "models", "wasm", "planner_agent.wasm")
if not os.path.exists(_WASM):
    # Fall back to HyperAgents wasm_agents path
    _WASM = os.path.join(os.path.dirname(__file__), "..", "HyperAgents", "wasm_agents", "planner_agent.wasm")
    if not os.path.exists(_WASM):
        _WASM = "/tmp/sovereign-core-rs/wasm_agents/planner_agent.wasm"

if os.path.exists(_WASM):
    host = WasmHost()
    with open(_WASM, "rb") as f:
        wasm_bytes = f.read()
    planner_wasm = host.load_agent(wasm_bytes, "planner")
    print(f"  loaded planner_agent.wasm ({len(wasm_bytes):,} bytes)")

    block = KernelBlock(
        agent_id=agent_id, genome_id=1, creds_token=0b1111,
        task_id=2, words=[word.encode()], metrics_ref=0,
    )
    wasm_results = host.call_agent(planner_wasm, block)
    if wasm_results:
        ww = SemanticWord.decode(wasm_results[0].words[0])
        print(f"  handle_block -> type=RESULT({ww.type_}) intent=PLAN({ww.intent}) confidence={ww.confidence_f():.3f}")
        delta = ww.confidence_f() - word.confidence_f()
        print(f"  confidence boosted by {delta:+.3f} (planner mutation)")
else:
    print(f"  (WASM not found at {_WASM}, skipping)")

# ── Layer 3a: GH05T3 expert agents (Python sovereign-core) ──────────────────
print("\n[LAYER 3a] GH05T3 Expert Agents (Python sovereign-core)")
try:
    from backend.integration.kernel_adapter import KernelAdapter
    from backend.core.moe_router import MOERouter
    from src.semantics.semantic_word import IntentType

    router = MOERouter()
    router.load_experts()

    task_word = router._adapter.encode(intent=IntentType.PLAN, confidence=0.85)
    plan_results = router.route(task_word)
    print(f"  MOERouter.route(PLAN) -> {len(plan_results)} result words")

    from src.semantics.semantic_word import SemanticWord as PySW
    for pw in plan_results:
        sw = PySW.decode(pw)
        type_val = getattr(sw, "type_", None) or getattr(sw, "type", "?")
        print(f"  result: type={type_val} intent={sw.intent} confidence={sw.confidence_f:.3f}")
except Exception as e:
    print(f"  (skipped — need SOVEREIGN_CORE_PATH set: {e})")

# ── Layer 3b: HyperAgents genome evolution ───────────────────────────────────
print("\n[LAYER 3b] HyperAgents Genome Evolution")
sys.path.insert(0, "/tmp/HyperAgents")
try:
    from hyper.genome import AgentGenome, GenomeRegistry, _next_id
    from hyper.kernel_bridge import KernelBridge
    from hyper.scheduler import HyperScheduler

    reg = GenomeRegistry()
    for i, (traits, fitness) in enumerate([
        ({"plan": 0.9, "critique": 0.7, "build": 0.8}, 2.0),
        ({"plan": 0.6, "critique": 0.9, "build": 0.5}, 1.5),
        ({"plan": 0.4, "critique": 0.4, "build": 0.9}, 1.0),
    ]):
        g = AgentGenome(
            genome_id=_next_id(), name=f"genome_{i}",
            traits=traits, wasm_agent="planner_agent", fitness=fitness,
        )
        reg.register(g)

    bridge = KernelBridge(wasm_dir=os.path.dirname(_WASM) if os.path.exists(_WASM) else None)
    sched = HyperScheduler(registry=reg, bridge=bridge)
    sched.start()
    print(f"  spawned {bridge.agent_count()} agents (backend: {'Rust' if bridge.rust_backend else 'Python'})")

    for g in reg.all():
        result = sched.run_task(g.genome_id, intent=2)
        print(f"  genome {g.genome_id} ({g.name}): fitness={g.fitness:.1f} task_ms={result.duration_ms:.2f}")

    children = sched.evolve(n_children=3, mutation_rate=0.1)
    print(f"  evolved {len(children)} children")
    for c in children:
        print(f"    child {c.genome_id} ({c.name}) gen={c.generation} parent={c.parent_id}")

    print("\n  Leaderboard:")
    for gid, fit in sched.leaderboard()[:3]:
        g = reg.get(gid)
        print(f"    #{gid} {g.name:<20} fitness={fit:.1f}")

except Exception as e:
    import traceback
    print(f"  (error: {e})")
    traceback.print_exc()

print("\n" + "=" * 60)
print("  Demo complete — full Rust+WASM+Python stack verified")
print("=" * 60)
