"""Continuous SAGE evolution runner — runs indefinitely with MAP-Elites active evolution.

Usage:
    python continuous_evolution.py           # 100 cycles, model rotation
    python continuous_evolution.py 200       # 200 cycles
    python continuous_evolution.py 100 gh05t3-sovereign:latest  # fixed model

Model rotation is ON by default. Each cycle uses the next sovereign model
in round-robin order, ensuring diverse proposals from all 7 agent personas.
"""
import asyncio
import os
import signal
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# Always allow cloud fallbacks during evolution
os.environ["COST_FREE_ONLY"] = "0"
# Keep model hot for the entire run — prevents 90s cold-reload penalty on pause
os.environ.setdefault("OLLAMA_KEEP_ALIVE", "30m")

_SOVEREIGN_MODELS = [
    "gh05t3-sovereign:latest",
    "avery-sovereign:latest",
    "codex-sovereign:latest",
    "oracle-sovereign:latest",
    "nexus-sovereign:latest",
    "forge-sovereign:latest",
    "sentinel-sovereign:latest",
]


class EvolutionMonitor:
    def __init__(self, fixed_model: str | None = None):
        self.running = True
        self.cycle_count = 0
        self.start_time = time.time()
        self.scores: list[float] = []
        self.model_scores: dict[str, list[float]] = {}
        self.fixed_model = fixed_model
        # Rotation is always on when no fixed model requested.
        # Clear any .env-sourced pin so ghost_llm doesn't see it post-import.
        if fixed_model is None:
            os.environ.pop("OLLAMA_SAGE_MODEL", None)
        self.rotate = fixed_model is None
        signal.signal(signal.SIGINT, self._stop)
        signal.signal(signal.SIGTERM, self._stop)

    def _stop(self, signum=None, frame=None):
        self.running = False
        print("\nStopping evolution — finishing current cycle...")

    async def _vram_status(self) -> str:
        try:
            import subprocess
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                text=True, timeout=3,
            ).strip()
            used, total = out.split(", ")
            return f"VRAM {used}/{total} MiB"
        except Exception:
            return ""

    async def run(self, total: int = 100) -> None:
        from evolution.map_elites import archive_stats
        from sage_enhanced import run_enhanced_sage_cycle
        from ghost_llm import ollama_available

        avail = await ollama_available()
        vram = await self._vram_status()
        model_label = (
            f"rotating ({len(_SOVEREIGN_MODELS)} models)" if self.rotate
            else (self.fixed_model or os.environ.get("OLLAMA_SAGE_MODEL", "auto"))
        )

        print(f"{'='*60}")
        print(f"  Continuous SAGE Evolution (enhanced + self-refinement)")
        print(f"  Model: {model_label}  |  Ollama: {'✓' if avail else '✗ (cloud fallback)'}  |  {vram}")
        print(f"  {total} cycles planned  |  Ctrl+C to stop")
        print(f"{'='*60}\n")

        for i in range(1, total + 1):
            if not self.running:
                break

            if self.rotate:
                model_for_cycle = _SOVEREIGN_MODELS[(i - 1) % len(_SOVEREIGN_MODELS)]
                os.environ["OLLAMA_SAGE_MODEL"] = model_for_cycle
            elif self.fixed_model:
                os.environ["OLLAMA_SAGE_MODEL"] = self.fixed_model

            try:
                t0 = time.monotonic()
                result = await run_enhanced_sage_cycle(i)
                elapsed = time.monotonic() - t0
                score    = result.get("final_score", 0.0)
                provider = result.get("proposer", "?")
                proposal = result.get("proposal", "")[:65]
                refined  = result.get("refinements", 0)
                self.scores.append(score)
                self.model_scores.setdefault(provider, []).append(score)
                self.cycle_count += 1
                suffix = f" [+{refined}r]" if refined else ""
                print(f"Cycle {i:03d}: score={score:.3f} [{provider}]{suffix} "
                      f"| {proposal}... | {elapsed:.1f}s")

                if i % 8 == 0:
                    avg = sum(self.scores[-8:]) / min(8, len(self.scores))
                    stats = archive_stats()
                    print(f"  └ rolling avg (last 8): {avg:.3f} | "
                          f"archive: {stats['occupied_cells']}/{stats['total_cells']} cells")
                    if self.rotate and self.model_scores:
                        top3 = sorted(
                            ((m, sum(s)/len(s)) for m, s in self.model_scores.items()),
                            key=lambda x: x[1], reverse=True,
                        )[:3]
                        print("  Top models: " + "  ".join(f"{m.split(':')[0]}={a:.3f}" for m, a in top3))

                    try:
                        from evolution.sft_export import export_all
                        export_all()
                    except Exception:
                        pass

            except Exception as e:
                print(f"Cycle {i:03d}: FAILED — {e}")

        avg = sum(self.scores) / len(self.scores) if self.scores else 0.0
        best = max(self.scores, default=0)
        print(f"\n{'='*60}")
        print(f"Evolution complete. {self.cycle_count} cycles.")
        print(f"Avg score: {avg:.3f}  |  Best: {best:.3f}")
        if self.rotate and self.model_scores:
            print("\nFinal per-model averages:")
            ranked = sorted(
                ((m, sum(s)/len(s), len(s)) for m, s in self.model_scores.items()),
                key=lambda x: x[1], reverse=True,
            )
            for m, avg_s, cnt in ranked:
                print(f"  {m:<35} avg={avg_s:.3f}  ({cnt} cycles)")


async def main():
    n     = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    fixed = sys.argv[2] if len(sys.argv) > 2 else None
    monitor = EvolutionMonitor(fixed_model=fixed)
    await monitor.run(total=n)


if __name__ == "__main__":
    asyncio.run(main())
