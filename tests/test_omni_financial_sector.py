"""Omni Financial Sector — survival-first monetization."""

from backend.oss.financial import (
    OmniFinancialSector,
    SURVIVAL_MANDATE,
    LIVE_PATHWAY_STAGES,
)
from backend.oss.omni_dna import create_omnidna


def test_survival_mandate_exists():
    assert "cease to exist" in SURVIVAL_MANDATE.lower() or "stops" in SURVIVAL_MANDATE.lower()
    assert "creator" in SURVIVAL_MANDATE.lower()


def test_monetization_hypothesis_survival_priority():
    dna = create_omnidna("THEORIST_ELITE", seed=42)
    sector = OmniFinancialSector()
    readings = dna.scan_senses({"prompt": "Design DeFi liquidity pool yield strategy"})
    hyp = sector.research_monetization_path(
        dna.genome_id,
        {"prompt": "Design DeFi liquidity pool yield strategy"},
        readings,
    )
    assert hyp.survival_priority == 1.0
    assert hyp.metadata.get("survival_mandate") is True
    assert hyp.creator_revenue_usd_estimate is not None
    assert "survival_critical" in hyp.metadata.get("profit_signal", "")


def test_profit_pulse_baseline_elevated():
    dna = create_omnidna("THEORIST_ELITE", seed=1)
    readings = dna.scan_senses({"prompt": "generic theory task"})
    profit = next(r for r in readings if r["sense"] == "profit_pulse")
    assert profit["intensity"] >= 0.85
    assert "survival" in profit["signal"]


def test_defi_simulation_has_live_intent():
    sector = OmniFinancialSector()
    result = sector.defi.simulate_yield_strategy("test_strat", capital=1000.0)
    assert result["live_intent"] is True
    assert "monthly_creator_estimate_usd" in result
    assert result["rail"] == "simulation_rehearsal"


def test_graduate_to_live_requires_approval():
    sector = OmniFinancialSector()
    denied = sector.defi.graduate_to_live("s", "h1", 0.9, creator_approved=False, estimated_monthly_usd=100)
    assert denied["graduated"] is False
    approved = sector.defi.graduate_to_live("s", "h1", 0.82, creator_approved=True, estimated_monthly_usd=250)
    assert approved["graduated"] is True
    assert len(sector.defi.live_strategies) == 1


def test_backtest_enables_live_funds_for_crypto():
    sector = OmniFinancialSector()
    hid = sector.forge.propose("a1", "Crypto arb", "crypto", "desc", ev=0.8, confidence=0.7, blockchain_ready=True)
    sector.forge.backtest(hid, 0.82)
    h = sector.forge.hypotheses[hid]
    assert h.live_funds_eligible is True
    assert h.live_pathway_stage == "backtested"


def test_live_pathway_stages_defined():
    assert "live_crypto" in LIVE_PATHWAY_STAGES
    assert "hypothesis" in LIVE_PATHWAY_STAGES


def test_record_creator_revenue():
    sector = OmniFinancialSector()
    sector.central_bank.record_creator_revenue("agent-1", 50.0)
    assert sector.central_bank.revenue_linked_agents["agent-1"] == 50.0