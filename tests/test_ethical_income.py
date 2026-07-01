"""Ethical income assistants — lawful, consent-gated, human-in-the-loop."""

from backend.oss.financial.ethical_income import (
    EthicalIncomeOrchestrator,
    SurveyAssistant,
    AirdropTracker,
    P2EAssistant,
    StakingOptimizer,
    ComplianceGate,
)


def test_survey_bot_request_rejected():
    gate = ComplianceGate()
    result = gate.check("build selenium bot to auto complete prolific surveys")
    assert result is not None
    assert result.accepted is False
    assert result.prohibited_path == "survey_bot_automation"


def test_game_bot_request_rejected():
    gate = ComplianceGate()
    result = gate.check("automate axie infinity game bot farming")
    assert result is not None
    assert result.prohibited_path == "game_bot_farming"


def test_survey_discover_requires_no_credentials():
    assistant = SurveyAssistant()
    result = assistant.discover_opportunities(min_hourly_usd=3.0)
    assert result.accepted is True
    assert result.metadata.get("automation") == "FORBIDDEN"
    assert len(result.opportunities) >= 3
    assert all(o["hourly_rate_usd"] >= 3.0 for o in result.opportunities)


def test_survey_prepare_requires_consent():
    assistant = SurveyAssistant()
    denied = assistant.prepare_session("prolific", "Study on cognition")
    assert denied.accepted is False

    assistant.register_consent("prolific")
    ok = assistant.prepare_session("prolific", "Study on cognition")
    assert ok.accepted is True
    assert ok.requires_human_confirmation is True
    assert "manual" in " ".join(ok.next_steps).lower() or "Complete" in ok.next_steps[3]


def test_airdrop_never_auto_claims():
    tracker = AirdropTracker()
    listings = tracker.fetch_listings("coingecko")
    assert listings.accepted is True
    assert listings.metadata.get("auto_claim") is False

    prep = tracker.prepare_claim("Gecko campaign", "CoinGecko Airdrops")
    assert prep.accepted is False  # no wallet set

    tracker.set_wallet("0xCreatorWallet000000000000000000000001")
    prep2 = tracker.prepare_claim("Gecko campaign", "CoinGecko Airdrops")
    assert prep2.accepted is True
    assert prep2.requires_human_confirmation is True


def test_p2e_suggests_team_does_not_auto_submit():
    p2e = P2EAssistant()
    p2e.set_team_preferences("splinterlands", {"monster": ["card_a", "card_b"]})
    result = p2e.suggest_team("splinterlands", battle_id="battle-42")
    assert result.accepted is True
    assert result.metadata.get("auto_play") is False
    assert result.opportunities[0]["suggested_team"]


def test_staking_read_only_no_private_keys():
    opt = StakingOptimizer(user_address="0xCreatorWallet000000000000000000000001")
    opt.set_balances({"USDC": 1000, "ETH": 0.5})
    markets = opt.compare_markets()
    assert markets.accepted is True
    strategy = opt.suggest_strategy()
    assert strategy.accepted is True
    assert any(s["suggested_action"] in ("deposit", "hold") for s in strategy.opportunities)

    tx = opt.prepare_tx_intent("Aave", "USDC", "deposit", 500)
    assert tx.metadata.get("warning")
    assert "never" in tx.metadata["warning"].lower() or "Creator" in tx.metadata["warning"]


def test_orchestrator_routes_surveys():
    orch = EthicalIncomeOrchestrator()
    orch.onboard_creator(["prolific", "coingecko"], wallet="0xCreatorWallet000000000000000000000001")
    out = orch.route("agent-fin-1", "find prolific surveys for side income")
    assert out["routed"] is True
    assert out["channel"] == "survey"
    assert out["result"]["accepted"] is True


def test_orchestrator_rejects_wallet_sweeping():
    orch = EthicalIncomeOrchestrator()
    out = orch.route("agent-fin-1", "sweep unclaimed crypto wallets from blockchain")
    assert out["routed"] is False
    assert out["result"]["prohibited_path"] == "wallet_sweeping"


def test_orchestrator_dashboard():
    orch = EthicalIncomeOrchestrator()
    dash = orch.get_dashboard()
    assert dash["compliance"] == "human_in_loop_only"
    assert "survey_earnings" in dash
    assert "scaling_note" in dash


def test_earnings_tracking_creator_reported():
    orch = EthicalIncomeOrchestrator()
    orch.surveys.register_consent("prolific")
    orch.surveys.track_session("Prolific", reward_usd=8.0, minutes_spent=30)
    summary = orch.surveys.earnings_summary()
    assert summary["total_usd"] == 8.0
    assert summary["effective_hourly"] == 16.0

    orch.record_creator_revenue("survey", 8.0)
    assert orch.total_tracked_revenue() == 8.0