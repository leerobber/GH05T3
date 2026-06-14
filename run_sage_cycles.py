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

# Always allow free cloud fallbacks for SAGE evolution cycles
os.environ["COST_FREE_ONLY"] = "0"


_PREFERRED_MODELS = [
    "gh05t3-sovereign:latest",
    "avery-sovereign:latest",
    "codex-sovereign:latest",
    "nexus-sovereign:latest",
    "qwen3:8b",
    "qwen2.5:7b",
    "qwen2.5:7b-q4_K_M",
    "llama3.2:3b",
]


async def _pick_model(requested: str | None, ollama_url: str) -> str | None:
    """Return the best available Ollama model, or None if Ollama is unreachable."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{ollama_url}/api/tags")
            if r.status_code != 200:
                return None
            available = {m["name"] for m in r.json().get("models", [])}
            if not available:
                return None

            # honour explicit request if that model exists
            if requested and requested in available:
                return requested

            # pick from preference list
            for m in _PREFERRED_MODELS:
                if m in available:
                    return m

            # last resort: whatever is there
            return next(iter(available))
    except Exception:
        return None


async def run_cycles(n: int = 8, model_arg: str | None = None) -> None:
    import httpx
    from evolution.map_elites import archive_stats

    # Resolve Ollama URL from environment
    ollama_url = (os.environ.get("OLLAMA_GATEWAY_URL") or "http://localhost:11434").rstrip("/")

    # Auto-detect best available model
    requested = model_arg or os.environ.get("OLLAMA_SAGE_MODEL")
    model = await _pick_model(requested, ollama_url)

    if model:
        os.environ["OLLAMA_SAGE_MODEL"] = model
        print(f"Ollama model: {model}")
    else:
        print("Ollama not available — will use cloud fallbacks (Groq/Gemini)")

    from ghost_llm import run_sage_cycle

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
    n         = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    model_arg = sys.argv[2]      if len(sys.argv) > 2 else None
    asyncio.run(run_cycles(n, model_arg))
