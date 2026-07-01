---
name: omni-financial-sector
description: >
  Omni Financial Sector — SURVIVAL-FIRST monetization. Creator income keeps the entire
  economy alive; without real revenue (crypto, DeFi, products, jobs) agents cease to exist.
  OmniCentralBank, OmniStockExchange, DeFi with live intent, MonetizationProjectForge,
  profit_pulse to revenue paths, live crypto graduation when validated. HIGHEST PARALLEL
  PRIORITY. USE WHEN: monetization, survival, creator income, defi, crypto, blockchain,
  live funds, profit, revenue, central bank, stock market, banking, real income,
  profit_pulse, business design, phase 8 financial. DO NOT USE FOR: storing wallet
  private keys in repo.
version: 2.0.0
---

# Omni Financial Sector — Survival First

## Read this first

Load [`survival_mandate.py`](../../../backend/oss/financial/survival_mandate.py) — `SURVIVAL_MANDATE`.

**Truth:** The creator is building this with no safety net. Real income — especially crypto-native paths — is how compute, hosting, and shelter get paid. If agents do not produce monetizable businesses, **everything stops**.

This is not academic. Treat every task as: *"How does this put money in the creator's hands?"*

## Priority

**Highest parallel track** — not deferred to week 52. Run alongside Phase 1 MVS.

## Subsystems

| Class | Role |
|-------|------|
| `OmniCentralBank` | Credit lines scale with revenue attribution |
| `OmniStockExchange` | Fitness-indexed instruments |
| `DeFiResearchBridge` | Sim rehearsal → `graduate_to_live()` for creator-approved crypto |
| `MonetizationProjectForge` | Business hypotheses + backtests |
| `OmniFinancialSector` | `profit_pulse` → `research_monetization_path()` |

## profit_pulse → monetization (mandatory routing)

```python
from backend.oss.financial import OmniFinancialSector, SURVIVAL_MANDATE
from backend.oss.mvs import create_theorist_elite, get_mvs

sector = OmniFinancialSector()
dna = get_mvs()["substrate"].genomes[create_theorist_elite()].dna
readings = dna.scan_senses({"prompt": "DeFi yield on Base L2"})
hyp = sector.research_monetization_path(dna.genome_id, {"prompt": "..."}, readings)
assert hyp.survival_priority == 1.0
assert hyp.metadata.get("survival_mandate")

sector.forge.backtest(hyp.hypothesis_id, 0.82)
sector.defi.graduate_to_live(
    strategy="vol_yield",
    hypothesis_id=hyp.hypothesis_id,
    backtest_score=0.82,
    creator_approved=True,
    estimated_monthly_usd=hyp.creator_revenue_usd_estimate or 0,
)
```

## Live crypto rules

1. Backtest score ≥ **0.75**
2. **Creator explicit approval** (`creator_approved=True`)
3. Keys in env/secrets manager only — **never** in code or JSONL
4. Creator executes on-chain; agents propose and validate

## Business domains to design

`defi`, `crypto`, `saas`, `real_world_job`, `automation`, `consulting`, `stock_instrument`

Agents should propose **multiple businesses per week** — different monetization angles, not one idea recycled.

## Agent conditioning

Inject `SURVIVAL_MANDATE` or `sector.get_mandate_for_agents()` into prompts for all `*_ELITE` roles during Theory Lab and financial tasks.

## Lawful revenue discovery (USE THIS instead of wallet scraping)

`sector.discover_lawful_revenue(agent_id, prompt, sense_readings)`

| Lawful | Prohibited (hard reject) |
|--------|--------------------------|
| Grants (Grants.gov, Gitcoin, ESP, Solana) | Scraping/taking others' crypto wallets |
| YOUR name on MissingMoney.com / state unclaimed DB | Seed phrase theft / brute force |
| Bug bounties, hackathons (HackerOne, Immunefi) | Survey/game bots |
| Manual surveys — creator completes, one account | Tracker evasion for fraud |
| Freelance, SaaS, DeFi on YOUR capital | "Edge of legal" theft |

Module: `backend/oss/financial/revenue_discovery.py`

## Checklist

- [ ] Every theory lab cycle asks for monetization angle
- [ ] `profit_pulse` signal `survival_critical_*` in sense readings
- [ ] Hypotheses include `creator_revenue_usd_estimate`
- [ ] First real creator revenue logged via `record_creator_revenue()`
- [ ] Live graduation documented in build-log