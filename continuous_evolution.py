"""Continuous SAGE evolution runner — runs indefinitely with MAP-Elites active evolution.

Usage:
    python continuous_evolution.py           # 100 cycles
    python continuous_evolution.py 200       # 200 cycles

Set OLLAMA_SAGE_MODEL env var:
    $env:OLLAMA_SAGE_MODEL = "gh05t3-sovereign:latest"
    python continuous_evolution.py
"""
import asyncio
import os
import signal
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# Always allow cloud fallbacks during evolution
os.environ["COST_FREE_ONLY"] = "0"


class EvolutionMonitor:
    def __init__(self):
        self.running = True
        self.cycle_count = 0
        self.start_time = time.time()
        self.scores: list[float] = []
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
        from ghost_llm import run_sage_cycle, ollama_available

        model = os.environ.get("OLLAMA_SAGE_MODEL", "auto")
        avail = await ollama_available()
        vram = await self._vram_status()

        print(f"{'='*60}")
        print(f"  Continuous SAGE Evolution")
        print(f"  Model: {model}  |  Ollama: {'✓' if avail else '✗ (cloud fallback)'}  |  {vram}")
        print(f"  {total} cycles planned  |  Ctrl+C to stop")
        print(f"{'='*60}\n")

        while self.running and self.cycle_count < total:
            self.cycle_count += 1
            try:
                t0 = time.monotonic()
                result = await run_sage_cycle(self.cycle_count, use_nightly=False)
                elapsed = time.monotonic() - t0
                score = result.get("final_score", 0.0)
                provider = result.get("proposer", "?")
                proposal = result.get("proposal", "")[:65]
                self.scores.append(score)

                print(f"Cycle {self.cycle_count:03d}: score={score:.3f} [{provider}] "
                      f"| {proposal}... | {elapsed:.1f}s")

                # Print archive stats every 8 cycles (when tell() batch flushes)
                if self.cycle_count % 8 == 0:
                    stats = archive_stats()
                    avg = sum(self.scores[-8:]) / min(8, len(self.scores))
                    vram = await self._vram_status()
                    print(f"\n--- Batch {self.cycle_count // 8} complete ---")
                    print(f"  Archive: {stats['occupied_cells']}/{stats['total_cells']} cells "
                          f"({stats['coverage_pct']}% coverage)")
                    print(f"  Best: {stats['best_objective']}  |  "
                          f"Mean: {stats['objective_mean']}  |  "
                          f"Elites: {stats['elite_count']}")
                    print(f"  Last 8 avg score: {avg:.3f}  |  {vram}\n")

            except Exception as e:
                print(f"Cycle {self.cycle_count:03d}: FAILED — {e}")

        # Final summary
        stats = archive_stats()
        total_time = time.time() - self.start_time
        avg_score = sum(self.scores) / len(self.scores) if self.scores else 0.0
        best_score = max(self.scores) if self.scores else 0.0

        print(f"\n{'='*60}")
        print(f"  Evolution complete — {self.cycle_count} cycles in {total_time:.0f}s "
              f"({total_time/max(self.cycle_count,1):.1f}s/cycle)")
        print(f"  Scores: avg={avg_score:.3f}  best={best_score:.3f}")
        print(f"  Archive: {stats['occupied_cells']}/{stats['total_cells']} cells "
              f"({stats['coverage_pct']}% coverage)")
        print(f"  Best objective: {stats['best_objective']}")
        print(f"  Elite proposals: {stats['elite_count']}")
        print(f"{'='*60}")


if __name__ == "__main__":
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    monitor = EvolutionMonitor()
    asyncio.run(monitor.run(total))
