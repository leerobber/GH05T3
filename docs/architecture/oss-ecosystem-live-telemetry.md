# oss/ecosystem: real telemetry, not the sandbox

**Status:** Accepted, live (commit `99d3a41`)

## Context

`oss/ecosystem/` implements a real, tested finite-state-machine model — a
7-state "global species" FSM, 5 role FSMs (scientist/builder/operator/
investor/governor), a 7-state Omni-Mind FSM, and a 6-state Omni-Economy
FSM — with real reward formulas in `rewards.py` matching the documented
math exactly. It's live: `POST /oss/oss/ecosystem/step` (mounted with a
doubled `/oss` prefix on purpose, see `oss/api/router.py`) actually
persists state to `data/oss_ecosystem.json` on every call.

Its reward inputs, however, came entirely from `oss/kernel/sandbox.py` —
a module whose own docstrings say "paper only" (`MarketSandbox`, a
synthetic random-walk price series) and "Fake services" (`InfraSandbox`,
simulated uptime/error-rate). Confirmed empirically before changing
anything: calling `ecosystem_step()` three times in a row produced an
identical `omni_mind` reward (`0.4617`) and `omni_economy` reward (`0.37`)
every time — because those specific inputs were unconditional hardcoded
constants in `orchestrator.py`'s context-builders, not measurements.

## Decision

New `oss/ecosystem/live_sources.py` replaces the sandbox with reads from
subsystems that were already real and already running elsewhere in this
repo, but never wired into the ecosystem orchestrator:

| Function | Real source | Feeds |
|---|---|---|
| `kairos_snapshot()` | `evolution.kairos.stats()` — real proposal scores, real SENTINEL blocks, real entropy drift | scientist, operator, governor |
| `treasury_metrics()` | Real Sharpe/drawdown/volatility computed over the real `SOVEREIGN_TREASURY` transaction history (`economy.ledger`) — same math `MarketSandbox.metrics()` used, applied to real deltas instead of a synthetic walk | investor |
| `builder_snapshot()` | Real Stripe subscriber counts + real settled NC revenue (`oss.monetization.stripe.settle_payment()` genuinely credits the ledger from real Stripe checkout events) | builder |

Every function is a best-effort read (try/except) returning `"live":
False` with a **neutral** constant on failure — not a randomly generated
one — so an idle KAIROS (0 cycles run) reports full uptime/efficiency
(`1.0`), not a fabricated failure (`0.0`).

Left as **documented, honest, neutral placeholders** — not faked: novelty,
memetic_fitness, harm_score, trait_utilization, desire_fulfillment,
`omni_mind.goal_completion`, and `_economy_context()`'s
trait_liquidity/memory_valuation/desire_fulfillment_rate/soul_bond_strength.
No working signal exists anywhere in this codebase for any of these yet —
inventing a formula for them would move the fabrication, not remove it.

## Consequences

- Live-verified: recording one real KAIROS cycle (score=0.95,
  sentinel_viability=0.9) between two `ecosystem_step()` calls moved
  scientist 0.155→0.6425, operator 0.55→0.7875, governor 0.5→0.815,
  investor 0.1→0.3 — while builder/omni_mind/omni_economy correctly held
  flat since nothing relevant to them changed in the same window.
- 517 passed / 57 pre-existing failures (confirmed via `git stash` to be
  identical with or without this change — missing GPU/triton and
  `saas_product_lab` fixture data, unrelated) / 18 skipped. 6 new tests
  added for `live_sources.py`.
- `oss/kernel/sandbox.py` itself was **not** deleted — `get_sandbox()`/
  `reset_sandbox()` still exist, just no longer called from
  `ecosystem_step()`. `tests/test_oss_ecosystem.py`'s now-pointless
  `reset_sandbox()` call was removed.
- This subsystem isn't listed in `docs/details/canonical-paths.md`'s
  "Genomic / MVS Layer" table — see
  [evolution-systems-inventory.md](evolution-systems-inventory.md).
