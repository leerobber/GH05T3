"""SAGE cycle runner — enhanced with self-refinement and knowledge grounding.

Usage:
    python run_sage_cycles.py              # 8 enhanced cycles
    python run_sage_cycles.py 16           # 16 cycles
    python run_sage_cycles.py 8 basic      # 8 cycles (basic mode, no self-refinement)

Set model:
    $env:OLLAMA_SAGE_MODEL = "gh05t3-sovereign:latest"
    python run_sage_cycles.py 8
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# Always allow cloud fallbacks for SAGE evolution cycles
os.environ["COST_FREE_ONLY"] = "0"


async def run_cycles(n: int = 8, mode: str = "enhanced") -> None:
    from evolution.map_elites import archive_stats
    from ghost_llm import ollama_available

    if mode == "enhanced":
        from sage_enhanced import run_enhanced_sage_cycle as _run_cycle
    else:
        from ghost_llm import run_sage_cycle as _base
        async def _run_cycle(i, **_):
            return await _base(i, use_nightly=False)

    model = os.environ.get("OLLAMA_SAGE_MODEL", "auto")
    avail = await ollama_available()

    if avail:
        print(f"Ollama: available  |  model: {model}  |  mode: {mode}")
    else:
        print(f"Ollama: not reachable  |  mode: {mode}  |  cloud fallback active")

    print(f"Running {n} SAGE cycles...\n")

    scores = []
    for i in range(1, n + 1):
        try:
            t0 = time.monotonic()
            result = await _run_cycle(i)
            elapsed = time.monotonic() - t0
            score    = result.get("final_score", 0.0)
            provider = result.get("proposer", "?")
            proposal = result.get("proposal", "")[:65]
            refined  = result.get("refinements", 0)
            scores.append(score)
            suffix = f" [+{refined}r]" if refined else ""
            print(f"Cycle {i:02d}: score={score:.3f} [{provider}]{suffix} "
                  f"| {proposal}... | {elapsed:.1f}s")
        except Exception as e:
            print(f"Cycle {i:02d}: FAILED — {e}")

    stats = archive_stats()
    avg = sum(scores) / len(scores) if scores else 0.0
    print(f"\n{'='*60}")
    print(f"Avg score: {avg:.3f}  |  Best: {max(scores, default=0):.3f}")
    print(f"MAP-Elites: {stats['occupied_cells']}/{stats['total_cells']} cells "
          f"({stats['coverage_pct']}% coverage) | "
          f"best={stats['best_objective']} | mean={stats['objective_mean']}")


if __name__ == "__main__":
    n    = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    mode = sys.argv[2] if len(sys.argv) > 2 else "enhanced"
    asyncio.run(run_cycles(n, mode))
