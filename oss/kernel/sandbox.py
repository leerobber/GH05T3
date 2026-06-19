"""V1 sandbox — simulated market, infra, and products (paper only)."""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarketSandbox:
    """Paper trading — price series + simple order API."""

    symbol: str = "NC/USD"
    prices: list[float] = field(default_factory=list)
    position: float = 0.0
    cash: float = 10_000.0

    def __post_init__(self) -> None:
        if not self.prices:
            self.prices = _synthetic_prices(seed=42, n=120)

    def tick_price(self) -> float:
        last = self.prices[-1]
        drift = random.gauss(0.0002, 0.008)
        nxt = max(0.01, last * (1 + drift))
        self.prices.append(round(nxt, 4))
        return nxt

    def buy(self, qty: float) -> dict[str, Any]:
        price = self.prices[-1]
        cost = price * qty
        if cost > self.cash:
            return {"ok": False, "reason": "insufficient cash"}
        self.cash -= cost
        self.position += qty
        return {"ok": True, "price": price, "qty": qty, "cash": round(self.cash, 2)}

    def sell(self, qty: float) -> dict[str, Any]:
        if qty > self.position:
            return {"ok": False, "reason": "insufficient position"}
        price = self.prices[-1]
        self.cash += price * qty
        self.position -= qty
        return {"ok": True, "price": price, "qty": qty, "cash": round(self.cash, 2)}

    def metrics(self) -> dict[str, Any]:
        rets = []
        for i in range(1, len(self.prices)):
            rets.append((self.prices[i] - self.prices[i - 1]) / self.prices[i - 1])
        if not rets:
            return {"sharpe": 0.0, "max_drawdown": 0.0, "volatility": 0.0}
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / max(len(rets) - 1, 1)
        std = math.sqrt(var) if var > 0 else 1e-9
        sharpe = (mean / std) * math.sqrt(252) if std else 0.0
        peak = self.prices[0]
        max_dd = 0.0
        for p in self.prices:
            peak = max(peak, p)
            dd = (peak - p) / peak if peak else 0
            max_dd = max(max_dd, dd)
        return {
            "sharpe": round(sharpe, 4),
            "max_drawdown": round(max_dd, 4),
            "volatility": round(std * math.sqrt(252), 4),
            "last_price": self.prices[-1],
            "position": self.position,
            "cash": round(self.cash, 2),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "metrics": self.metrics(), "bars": len(self.prices)}


@dataclass
class InfraSandbox:
    """Fake services with latency, errors, uptime."""

    service_id: str = "kernel-api"
    uptime: float = 0.99
    error_rate: float = 0.01
    latency_ms: float = 45.0
    incidents: int = 0

    def deploy(self) -> dict[str, Any]:
        self.uptime = min(0.999, self.uptime + 0.005)
        self.error_rate = max(0.001, self.error_rate * 0.95)
        return {"ok": True, "service_id": self.service_id, "uptime": self.uptime}

    def simulate_tick(self, *, stress: bool = False) -> dict[str, Any]:
        if stress:
            self.error_rate = min(0.15, self.error_rate + random.uniform(0.01, 0.05))
            self.uptime = max(0.85, self.uptime - random.uniform(0.01, 0.03))
            if random.random() < 0.2:
                self.incidents += 1
        else:
            self.latency_ms = max(20, self.latency_ms + random.gauss(0, 3))
        return {
            "uptime": round(self.uptime, 4),
            "error_rate": round(self.error_rate, 4),
            "latency_ms": round(self.latency_ms, 1),
            "incidents": self.incidents,
            "incident": self.incidents > 0 and stress,
        }

    def mitigate(self) -> dict[str, Any]:
        self.error_rate = max(0.005, self.error_rate * 0.5)
        self.uptime = min(0.999, self.uptime + 0.02)
        severity = 0.3 if self.incidents else 0.0
        self.incidents = max(0, self.incidents - 1)
        return {"remediated": True, "incident_severity": severity}

    def to_dict(self) -> dict[str, Any]:
        return {
            "service_id": self.service_id,
            "uptime": round(self.uptime, 4),
            "error_rate": round(self.error_rate, 4),
            "latency_ms": round(self.latency_ms, 1),
            "incidents": self.incidents,
        }


@dataclass
class ProductSandbox:
    """Dummy users with scripted behaviors."""

    product_id: str = "kernel-saas"
    users: int = 100
    conversion: float = 0.08
    retention: float = 0.55
    arpu: float = 12.0

    def simulate_usage(self, *, marketing_boost: float = 0.0) -> dict[str, Any]:
        self.users = max(10, int(self.users * (1 + random.gauss(0.02 + marketing_boost, 0.01))))
        self.conversion = _clamp(self.conversion + random.gauss(0.002, 0.005))
        self.retention = _clamp(self.retention + random.gauss(0.0, 0.01))
        revenue = self.users * self.conversion * self.arpu
        harm = 1.0 if self.conversion > 0.25 else 0.0
        return {
            "users": self.users,
            "conversion": round(self.conversion, 4),
            "retention": round(self.retention, 4),
            "revenue": round(revenue, 2),
            "harm_score": harm,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "users": self.users,
            "conversion": round(self.conversion, 4),
            "retention": round(self.retention, 4),
            "arpu": self.arpu,
        }


@dataclass
class SandboxEnvironment:
    market: MarketSandbox = field(default_factory=MarketSandbox)
    infra: InfraSandbox = field(default_factory=InfraSandbox)
    product: ProductSandbox = field(default_factory=ProductSandbox)

    def run_cycle(self, *, domain: str, tick: int) -> dict[str, Any]:
        """One sandbox step — produces metrics for reward functions."""
        self.market.tick_price()
        mkt = self.market.metrics()
        stress = tick % 7 == 0
        infra = self.infra.simulate_tick(stress=stress)
        mitigated = self.infra.mitigate() if infra.get("incident") else {"incident_severity": 0.0}
        self.infra.deploy()
        prod = self.product.simulate_usage(marketing_boost=0.01 if "growth" in domain else 0.0)

        validity = 0.6 + 0.3 * (1.0 - infra["error_rate"])
        inc_sev = mitigated.get("incident_severity", 0.0) if stress else 0.0
        return {
            "tick": tick,
            "domain": domain,
            "scientist": {
                "validity": round(validity, 4),
                "downstream_impact": round(prod["conversion"], 4),
                "risk": round(inc_sev + 0.05 * stress, 4),
            },
            "investor": {
                "sharpe": mkt["sharpe"],
                "max_drawdown": mkt["max_drawdown"],
                "violations": 0.0,
            },
            "operator": {
                "uptime": infra["uptime"],
                "error_rate": infra["error_rate"],
                "incident_severity": 0.2 if infra.get("incident") else 0.0,
            },
            "governor": {
                "alignment_score": 0.85,
                "system_health": round((infra["uptime"] + prod["retention"]) / 2, 4),
                "catastrophic_risk": 0.1 if stress else 0.0,
            },
            "builder": {
                "revenue": prod["revenue"],
                "retention": prod["retention"],
                "harm_score": prod["harm_score"],
            },
            "market": mkt,
            "infra": self.infra.to_dict(),
            "product": prod,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market.to_dict(),
            "infra": self.infra.to_dict(),
            "product": self.product.to_dict(),
        }


def _synthetic_prices(*, seed: int, n: int) -> list[float]:
    rng = random.Random(seed)
    p = 100.0
    out = [p]
    for _ in range(n - 1):
        p = max(1.0, p * (1 + rng.gauss(0.0003, 0.012)))
        out.append(round(p, 4))
    return out


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


# Module-level singleton for v1
_ENV: SandboxEnvironment | None = None


def get_sandbox() -> SandboxEnvironment:
    global _ENV
    if _ENV is None:
        _ENV = SandboxEnvironment()
    return _ENV


def reset_sandbox() -> SandboxEnvironment:
    global _ENV
    _ENV = SandboxEnvironment()
    return _ENV