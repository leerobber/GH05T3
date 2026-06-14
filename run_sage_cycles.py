"""SAGE cycle runner — enhanced with self-refinement and knowledge grounding.

Usage:
    python run_sage_cycles.py              # 8 enhanced cycles, model rotation
    python run_sage_cycles.py 16           # 16 cycles
    python run_sage_cycles.py 8 basic      # 8 cycles (basic mode, no self-refinement)
    python run_sage_cycles.py 8 enhanced gh05t3-sovereign:latest  # fixed model

Sovereign model rotation (default):
    Cycles rotate through all 7 sovereign models automatically, giving the
    archive diverse proposals from different agent perspectives.
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# Always allow cloud fallbacks for SAGE evolution cycles
os.environ["COST_FREE_ONLY"] = "0"

# Sovereign model roster — rotate through all agents for diversity
_SOVEREIGN_MODELS = [
    "gh05t3-sovereign:latest",
    "avery-sovereign:latest",
    "codex-sovereign:latest",
    "oracle-sovereign:latest",
    "nexus-sovereign:latest",
    "forge-sovereign:latest",
    "sentinel-sovereign:latest",
]


async def run_cycles(n: int = 8, mode: str = "enhanced",
                     fixed_model: str | None = None) -> None:
    from evolution.map_elites import archive_stats
    from ghost_llm import ollama_available

    if mode == "enhanced":
        from sage_enhanced import run_enhanced_sage_cycle as _run_cycle
    else:
        from ghost_llm import run_sage_cycle as _base
        async def _run_cycle(i, **_):
            return await _base(i, use_nightly=False)

    rotate = fixed_model is None and not os.environ.get("OLLAMA_SAGE_MODEL")
    avail = await ollama_available()

    if avail:
        if rotate:
            print(f"Ollama: available  |  model: rotating ({len(_SOVEREIGN_MODELS)} models)  |  mode: {mode}")
        else:
            model = fixed_model or os.environ.get("OLLAMA_SAGE_MODEL", "auto")
            print(f"Ollama: available  |  model: {model}  |  mode: {mode}")
    else:
        print(f"Ollama: not reachable  |  mode: {mode}  |  cloud fallback active")

    print(f"Running {n} SAGE cycles...\n")

    scores = []
    model_scores: dict[str, list[float]] = {}

    for i in range(1, n + 1):
        if rotate:
            model_for_cycle = _SOVEREIGN_MODELS[(i - 1) % len(_SOVEREIGN_MODELS)]
            os.environ["OLLAMA_SAGE_MODEL"] = model_for_cycle
        elif fixed_model:
            os.environ["OLLAMA_SAGE_MODEL"] = fixed_model

        try:
            t0 = time.monotonic()
            result = await _run_cycle(i)
            elapsed = time.monotonic() - t0
            score    = result.get("final_score", 0.0)
            provider = result.get("proposer", "?")
            proposal = result.get("proposal", "")[:65]
            refined  = result.get("refinements", 0)
            scores.append(score)
            model_scores.setdefault(provider, []).append(score)
            suffix = f" [+{refined}r]" if refined else ""
            print(f"Cycle {i:02d}: score={score:.3f} [{provider}]{suffix} "
                  f"| {proposal}... | {elapsed:.1f}s")
        except Exception as e:
            print(f"Cycle {i:02d}: FAILED — {e}")

    stats = archive_stats()
    avg = sum(scores) / len(scores) if scores else 0.0
    best = max(scores, default=0)
    print(f"\n{'='*60}")
    print(f"Avg score: {avg:.3f}  |  Best: {best:.3f}")
    print(f"MAP-Elites: {stats['occupied_cells']}/{stats['total_cells']} cells "
          f"({stats['coverage_pct']}% coverage) | "
          f"best={stats['best_objective']} | mean={stats['objective_mean']}")

    if rotate and model_scores:
        print("\nPer-model averages:")
        ranked = sorted(
            ((m, sum(s)/len(s), len(s)) for m, s in model_scores.items()),
            key=lambda x: x[1], reverse=True,
        )
        for m, avg_s, cnt in ranked:
            print(f"  {m:<35} avg={avg_s:.3f}  ({cnt} cycles)")


if __name__ == "__main__":
    n    = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    mode = sys.argv[2] if len(sys.argv) > 2 else "enhanced"
    fixed = sys.argv[3] if len(sys.argv) > 3 else None
    asyncio.run(run_cycles(n, mode, fixed))
