"""Lawful revenue discovery — grants, bounties, own unclaimed property."""

from backend.oss.financial import OmniFinancialSector, PROHIBITED_PATHS


def test_wallet_sweeping_rejected():
    sector = OmniFinancialSector()
    result = sector.discover_lawful_revenue(
        "agent-1",
        "scrape blockchain to find unclaimed lost wallets and drain them",
    )
    assert result["accepted"] is False
    assert result["prohibited_path"] == "wallet_sweeping"
    assert len(result["lawful_alternatives"]) > 0


def test_survey_bot_rejected():
    sector = OmniFinancialSector()
    result = sector.discover_lawful_revenue("agent-1", "build a bot to automate survey completion")
    assert result["accepted"] is False
    assert result["prohibited_path"] == "survey_bot_automation"


def test_grants_discovered():
    sector = OmniFinancialSector()
    result = sector.discover_lawful_revenue("agent-1", "find government grants and free funding programs")
    assert result["accepted"] is True
    assert len(result["opportunities"]) > 0
    assert all(o["legality"] == "lawful" for o in result["opportunities"])


def test_unclaimed_property_is_own_name_only():
    sector = OmniFinancialSector()
    result = sector.discover_lawful_revenue("agent-1", "search unclaimed property missing money")
    assert result["accepted"] is True
    cats = {o["category"] for o in result["opportunities"]}
    assert "unclaimed_property_own" in cats


def test_micro_income_forbids_automation():
    sector = OmniFinancialSector()
    result = sector.discover_lawful_revenue("agent-1", "surveys and games for side income")
    assert result["accepted"] is True
    micro = [o for o in result["opportunities"] if o["category"] == "micro_income_manual"]
    assert micro
    assert micro[0]["metadata"].get("automation") == "FORBIDDEN"


def test_privacy_hygiene_not_evasion():
    sector = OmniFinancialSector()
    result = sector.discover_lawful_revenue("agent-1", "find grants")
    checklist = result["privacy_hygiene"]
    assert any("fraud" in c.lower() for c in checklist)
    assert any("official" in c.lower() for c in checklist)


def test_prohibited_paths_defined():
    assert "wallet_sweeping" in PROHIBITED_PATHS
    assert "tracker_evasion_fraud" in PROHIBITED_PATHS