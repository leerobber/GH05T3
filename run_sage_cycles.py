"""Runner script: execute N SAGE cycles with MAP-Elites active evolution.

Usage:
    python run_sage_cycles.py              # 8 cycles
    python run_sage_cycles.py 16           # 16 cycles

Set OLLAMA_SAGE_MODEL env var to pick the model:
    $env:OLLAMA_SAGE_MODEL = "gh05t3-sovereign:latest"
    python run_sage_cycles.py 8
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# Allow cloud fallbacks (Groq/Gemini) during evolution cycles
os.environ["COST_FREE_ONLY"] = "0"


async def run_cycles(n: int = 8) -> None:
    from evolution.map_elites import archive_stats
    from ghost_llm import run_sage_cycle, ollama_available

    # Show which model will be used
    model = os.environ.get("OLLAMA_SAGE_MODEL", "auto")
    avail = await ollama_available()

    if avail:
        print(f"Ollama: available  |  model: {model}")
    else:
        print("Ollama: not reachable — will use cloud fallbacks (Groq/Gemini)")

    print(f"Running {n} SAGE cycles...\n")

    for i in range(1, n + 1):
        try:
            t0 = time.monotonic()
            result = await run_sage_cycle(i, use_nightly=False)
            elapsed = time.monotonic() - t0
            score    = result.get("final_score", 0.0)
            provider = result.get("proposer", "?")
            proposal = result.get("proposal", "")[:65]
            print(f"Cycle {i:02d}: score={score:.3f} [{provider}] | {proposal}... | {elapsed:.1f}s")
        except Exception as e:
            print(f"Cycle {i:02d}: FAILED — {e}")

    stats = archive_stats()
    print(f"\n{'='*60}")
    print(f"MAP-Elites: {stats['occupied_cells']}/{stats['total_cells']} cells "
          f"({stats['coverage_pct']}% coverage) | "
          f"best={stats['best_objective']} | mean={stats['objective_mean']}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    asyncio.run(run_cycles(n))
