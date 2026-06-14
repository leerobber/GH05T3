"""Runner script: execute N SAGE cycles with MAP-Elites active evolution.

Usage:
    python run_sage_cycles.py              # 8 cycles
    python run_sage_cycles.py 16           # 16 cycles
    python run_sage_cycles.py 8 gh05t3-sovereign:latest

Set OLLAMA_SAGE_MODEL env var to override the model.
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))


async def run_cycles(n: int = 8, model: str | None = None) -> None:
    if model:
        os.environ["OLLAMA_SAGE_MODEL"] = model
    # Always allow free cloud fallbacks (Groq, Gemini) for SAGE evolution cycles
    os.environ["COST_FREE_ONLY"] = "0"

    from evolution.map_elites import archive_stats
    from ghost_llm import ollama_available, run_sage_cycle

    print("Checking Ollama...")
    if not await ollama_available():
        print("ERROR: Ollama not running. Start with: ollama serve")
        return

    sage_model = os.environ.get("OLLAMA_SAGE_MODEL", "gh05t3-sovereign:latest")
    print(f"Running {n} SAGE cycles with {sage_model}...\n")

    for i in range(1, n + 1):
        try:
            t0 = time.monotonic()
            result = await run_sage_cycle(i, use_nightly=False)
            elapsed = time.monotonic() - t0
            score    = result.get("final_score", 0.0)
            proposal = result.get("proposal", "")[:70]
            print(f"Cycle {i:02d}: score={score:.3f} | {proposal}... | {elapsed:.1f}s")
        except Exception as e:
            print(f"Cycle {i:02d}: FAILED — {e}")

    stats = archive_stats()
    print(f"\n{'='*60}")
    print(f"MAP-Elites archive: {stats['occupied_cells']}/{stats['total_cells']} cells "
          f"({stats['coverage_pct']}% coverage)")
    print(f"Best objective:     {stats['best_objective']}")
    print(f"Mean objective:     {stats['objective_mean']}")
    print(f"Elite count:        {stats['elite_count']}")


if __name__ == "__main__":
    n     = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    model = sys.argv[2]      if len(sys.argv) > 2 else None
    asyncio.run(run_cycles(n, model))
