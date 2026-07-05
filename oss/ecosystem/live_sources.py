"""Real, non-simulated inputs for oss/ecosystem/orchestrator.py's reward
formulas -- replaces oss/kernel/sandbox.py's synthetic Market/Infra/Product
simulators (random-walk prices, fake uptime/error-rate, dummy scripted
users) with reads from subsystems that are already real and already
running elsewhere in this repo:

- KAIROS cycle history (backend/evolution/kairos.py) -- real proposal
  scores, real SENTINEL safety-gate blocks, real entropy drift. Feeds
  scientist/operator/governor.
- The real NeuroCoin/economy ledger (backend/economy/ledger.py), which
  oss/monetization/stripe.py's settle_payment() genuinely credits from
  real Stripe checkout events. Feeds investor/builder.
- Real Stripe subscriber records (backend/integrations/stripe_integration.py).
  Feeds builder retention.

Every function here is a best-effort read guarded by try/except, the same
convention oss/ecosystem/orchestrator.py's existing _mind_context()/
_economy_context() already use. On failure it returns "live": False with
NEUTRAL constants -- not randomly generated ones -- so a caller can tell
"nothing real available yet" apart from "measured, and it's actually
neutral". The old sandbox always fabricated a plausible-looking number
either way, which is exactly the failure mode this replaces.

What's still NOT real, on purpose rather than by omission: there is no
working signal anywhere in this codebase for novelty, memetic_fitness,
trait_liquidity, memory_valuation, desire_fulfillment, or soul-bond
strength. Those stay fixed neutral placeholders where they're used
(oss/ecosystem/orchestrator.py), clearly labeled as such -- inventing a
formula for them here would just move the fabrication, not remove it.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

TREASURY_AGENT = "SOVEREIGN_TREASURY"


def kairos_snapshot() -> dict[str, Any]:
    """Real KAIROS cycle history: proposal scores, SENTINEL blocks, entropy
    drift. No cycles run yet is treated as "fully healthy, nothing tried"
    (uptime/efficiency 1.0), not as "down" (0.0) -- an idle system isn't a
    failing one.
    """
    try:
        from evolution import kairos

        ks = kairos.stats()
        total = int(ks.get("total_cycles", 0))
        elite = int(ks.get("elite_cycles", 0))
        blocked = int(ks.get("sentinel_blocks", 0))
        block_ratio = round(blocked / total, 4) if total else 0.0
        return {
            "live": True,
            "total_cycles": total,
            "elite_ratio": round(elite / total, 4) if total else 0.0,
            "block_ratio": block_ratio,
            "avg_score": float(ks.get("avg_score", 0.0)),
            "avg_sentinel_v": float(ks.get("avg_sentinel_v", 0.0)),
            "avg_entropy_drift": float(ks.get("avg_entropy_drift", 0.0)),
        }
    except Exception:
        return {
            "live": False,
            "total_cycles": 0,
            "elite_ratio": 0.0,
            "block_ratio": 0.0,
            "avg_score": 0.0,
            "avg_sentinel_v": 0.0,
            "avg_entropy_drift": 0.0,
        }


def treasury_metrics() -> dict[str, Any]:
    """Real Sharpe/drawdown-style risk measure computed over the real
    SOVEREIGN_TREASURY transaction history -- same math
    oss/kernel/sandbox.py's MarketSandbox.metrics() used, applied to real
    ledger deltas instead of a synthetic price walk. With 0 or 1 real
    transactions there's no real variance to measure yet, so this reports
    a neutral (not fabricated) baseline rather than a computed-looking
    number from nothing.
    """
    try:
        from oss.economy.neuro_coin import get_neuro_coin

        nc = get_neuro_coin()
        balance = nc.balance(TREASURY_AGENT)
        tx = nc.history(TREASURY_AGENT, limit=100)
        deltas = [t.delta for t in reversed(tx)]  # oldest -> newest

        if len(deltas) < 2:
            return {
                "live": True,
                "treasury_balance": balance,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
                "volatility": 0.0,
                "transaction_count": len(deltas),
            }

        mean = sum(deltas) / len(deltas)
        var = sum((d - mean) ** 2 for d in deltas) / max(len(deltas) - 1, 1)
        std = math.sqrt(var) if var > 0 else 0.0
        sharpe = (mean / std) if std else 0.0

        running = balance - sum(deltas)  # balance before this window
        peak = running
        max_dd = 0.0
        for d in deltas:
            running += d
            peak = max(peak, running)
            if peak > 0:
                max_dd = max(max_dd, (peak - running) / peak)

        return {
            "live": True,
            "treasury_balance": balance,
            "sharpe": round(sharpe, 4),
            "max_drawdown": round(max_dd, 4),
            "volatility": round(std, 4),
            "transaction_count": len(deltas),
        }
    except Exception:
        return {
            "live": False,
            "treasury_balance": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "volatility": 0.0,
            "transaction_count": 0,
        }


def builder_snapshot() -> dict[str, Any]:
    """Real Stripe subscriber counts for retention, real settled-revenue
    (NC credited by oss.monetization.stripe.settle_payment() from actual
    Stripe checkout events) for revenue. No subscribers yet -> retention
    0.0, not a fabricated non-zero default.
    """
    try:
        from integrations.stripe_integration import subscriber_count
        from oss.economy.neuro_coin import get_neuro_coin

        sc = subscriber_count()
        total = int(sc.get("total", 0))
        active = int(sc.get("active", 0))
        retention = round(active / total, 4) if total else 0.0
        revenue_nc = get_neuro_coin().stats().get("total_issued", 0.0)
        return {
            "live": True,
            "retention": retention,
            "revenue": revenue_nc,
            "active_subscribers": active,
            "total_subscribers": total,
        }
    except Exception:
        return {
            "live": False,
            "retention": 0.0,
            "revenue": 0.0,
            "active_subscribers": 0,
            "total_subscribers": 0,
        }
