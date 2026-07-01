#!/usr/bin/env python3
"""
gh05t3 attention — CLI for MA-INBL attention operations.

Subcommands:
  run       Run attention forward pass on domain trait vectors
  profile   Benchmark numpy vs Triton backends
  evolve    Run LivingLoop attention evolution cycle
  triton    Show Triton availability and kernel info
  telemetry Dump recent attention telemetry
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── subcommand handlers ───────────────────────────────────────────────────────

def cmd_run(args: argparse.Namespace) -> int:
    """Run attention forward pass for a domain using genome trait vectors."""
    import numpy as np
    from oss.forge.attention_scorer import (
        AttentionDomainScorer,
        score_strands_for_domain,
        domain_trait_vector,
        _DOMAIN_TRAIT_WEIGHTS,
    )

    domain = args.domain
    n = max(1, args.n)
    seed = args.seed

    print(f"Running MA-INBL attention — domain={domain!r}, n_candidates={n}")

    # Generate random candidate trait dicts
    rng = __import__("random").Random(seed)
    from oss.substrate.attention_config import CANONICAL_TRAITS
    candidates = []
    for _ in range(n):
        traits = {t: round(rng.random(), 3) for t in rng.sample(CANONICAL_TRAITS, k=8)}
        candidates.append({"traits": traits, "fitness": round(rng.uniform(0.3, 0.9), 3)})

    t0 = time.perf_counter()
    ranked = score_strands_for_domain(domain, candidates)
    elapsed = time.perf_counter() - t0

    result = {
        "domain": domain,
        "n_candidates": n,
        "elapsed_ms": round(elapsed * 1000, 2),
        "ranked": [
            {"rank": i, "score": round(score, 4), "traits": strand.get("traits", {})}
            for i, (score, strand) in enumerate(ranked)
        ],
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    """Benchmark numpy vs Triton backends on small and medium sequence lengths."""
    import numpy as np
    from oss.attention.kernel import TRITON_AVAILABLE
    from oss.attention.attention import MA_INBLAttention

    shapes = [(8, 32), (32, 32), (64, 32)]
    rng = np.random.default_rng(0)

    results = {"triton_available": TRITON_AVAILABLE, "benchmarks": []}

    for seq, dim in shapes:
        x = rng.standard_normal((seq, dim)).astype(np.float32)
        row: dict = {"seq": seq, "dim": dim}

        # numpy
        m_np = MA_INBLAttention(embed_dim=dim, num_heads=4, backend="numpy")
        t0 = time.perf_counter()
        for _ in range(10):
            m_np.forward(x)
        row["numpy_ms"] = round((time.perf_counter() - t0) * 100, 3)

        # triton
        if TRITON_AVAILABLE:
            try:
                m_tr = MA_INBLAttention(embed_dim=dim, num_heads=4, backend="triton")
                t0 = time.perf_counter()
                for _ in range(10):
                    m_tr.forward(x)
                row["triton_ms"] = round((time.perf_counter() - t0) * 100, 3)
                row["speedup"] = round(row["numpy_ms"] / row["triton_ms"], 2)
            except Exception as exc:
                row["triton_error"] = str(exc)
        else:
            row["triton_ms"] = None
            row["note"] = "triton not available"

        results["benchmarks"].append(row)

    print(json.dumps(results, indent=2))
    return 0


def cmd_evolve(args: argparse.Namespace) -> int:
    """Run LivingLoop attention evolution cycle for a domain."""
    from oss.living_loop.experiments import attention_evolution_cycle

    domain = args.domain
    cycles = max(1, args.cycles)
    pop = max(2, args.population)

    print(f"Running attention evolution — domain={domain!r}, cycles={cycles}, pop={pop}")
    result = attention_evolution_cycle(
        domain=domain,
        n_cycles=cycles,
        population_size=pop,
        log_telemetry=args.log_telemetry,
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_triton(args: argparse.Namespace) -> int:
    """Show Triton availability, version, and kernel info."""
    from oss.attention.kernel import TRITON_AVAILABLE

    info: dict = {
        "triton_available": TRITON_AVAILABLE,
        "numpy_backend": "always_available",
    }

    if TRITON_AVAILABLE:
        try:
            import triton
            import torch
            info["triton_version"] = triton.__version__
            info["torch_version"] = torch.__version__
            info["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                info["cuda_device"] = torch.cuda.get_device_name(0)
        except Exception as exc:
            info["error"] = str(exc)
    else:
        info["note"] = (
            "Triton is not installed. Install triton + torch to enable GPU kernels. "
            "All attention operations fall back to the numpy reference implementation."
        )

    # Kernel info
    info["kernels"] = {
        "_binary_linear_packed": "XNOR+popcount binary matmul (Triton)",
        "ma_inbl_attention_kernel": "Fused MA-INBL attention with MGC + ORS (Triton)",
        "ma_inbl_attention_np": "Full MA-INBL reference (numpy, always available)",
    }

    print(json.dumps(info, indent=2))
    return 0


def cmd_telemetry(args: argparse.Namespace) -> int:
    """Dump recent attention telemetry from the JSONL log."""
    from oss.attention.telemetry import AttentionTelemetrySink

    sink = AttentionTelemetrySink()
    n = max(1, args.n)

    try:
        entries = sink.load_all()[-n:]
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    if not entries:
        print(json.dumps({"entries": [], "count": 0}))
        return 0

    summary = sink.summary()
    print(json.dumps({"entries": entries, "count": len(entries), "summary": summary}, indent=2))
    return 0


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="GH05T3 attention CLI — MA-INBL attention operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    # run
    p_run = sub.add_parser("run", help="Run attention forward pass on domain trait vectors")
    p_run.add_argument("--domain", default="general_cognition", help="Forge domain key")
    p_run.add_argument("--n", type=int, default=8, help="Number of candidate genomes")
    p_run.add_argument("--seed", type=int, default=42)

    # profile
    p_prof = sub.add_parser("profile", help="Benchmark numpy vs Triton backends")

    # evolve
    p_evo = sub.add_parser("evolve", help="Run LivingLoop attention evolution")
    p_evo.add_argument("--domain", default="general_cognition")
    p_evo.add_argument("--cycles", type=int, default=5)
    p_evo.add_argument("--population", type=int, default=4)
    p_evo.add_argument("--log-telemetry", action="store_true")

    # triton
    p_tri = sub.add_parser("triton", help="Show Triton availability and kernel info")

    # telemetry
    p_tel = sub.add_parser("telemetry", help="Dump recent attention telemetry")
    p_tel.add_argument("--n", type=int, default=20, help="Number of recent entries")

    args = ap.parse_args()

    handlers = {
        "run": cmd_run,
        "profile": cmd_profile,
        "evolve": cmd_evolve,
        "triton": cmd_triton,
        "telemetry": cmd_telemetry,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
