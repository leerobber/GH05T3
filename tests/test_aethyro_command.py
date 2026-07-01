"""Aethyro.com revenue HQ — WEB_ENGINEER_ELITE and command layer."""

from backend.oss.mvs import create_web_engineer_elite
from backend.oss.aethyro import (
    AethyroCommand,
    AETHYRO_DOMAIN,
    AETHYRO_BASE_URL,
    TrustSignalEngine,
    AethyroMonetizationStack,
)
from backend.oss.elite_lineages import EliteLineageManager


def test_domain_constants():
    assert AETHYRO_DOMAIN == "aethyro.com"
    assert AETHYRO_BASE_URL == "https://aethyro.com"


def test_web_engineer_elite_species():
    gid = create_web_engineer_elite(seed=99)
    assert gid
    from backend.oss.mvs import get_mvs
    rec = get_mvs()["substrate"].genomes[gid]
    assert "WEB_ENGINEER" in rec.role.upper()
    assert rec.dna.hyper_elite_senses is not None
    assert "Aethyro.com" in rec.dna.to_prompt()


def test_enterprise_mission():
    gid = create_web_engineer_elite(seed=1)
    cmd = AethyroCommand()
    mission = cmd.create_enterprise_redesign_mission(gid)
    assert cmd.domain == "aethyro.com"
    assert "aethyro.com" in mission.metadata.get("domain", cmd.domain)
    assert "seo" in mission.site_agents
    assert "stripe" in mission.site_agents
    assert "stripe_services" in mission.revenue_channels
    assert len(mission.trust_signals) >= 5


def test_trust_scorecard():
    engine = TrustSignalEngine()
    empty = engine.build_scorecard([])
    assert empty.overall_score == 0.0
    assert len(empty.critical_gaps) > 0

    partial = engine.build_scorecard(["ssl_https", "privacy_policy", "live_demo"])
    assert partial.overall_score > 0.0


def test_monetization_prioritizes_stripe_first():
    stack = AethyroMonetizationStack()
    channels = stack.prioritize_for_traffic(monthly_visitors=0)
    assert channels[0].channel_id == "stripe_services"


def test_ads_recommendation_by_traffic():
    stack = AethyroMonetizationStack()
    low = stack.recommend_ads_network(5000)
    assert "AdSense" in low["network"]
    high = stack.recommend_ads_network(60000)
    assert "Mediavine" in high["network"] or "Ezoic" in high["network"]


def test_assign_web_engineer_task():
    gid = create_web_engineer_elite(seed=2)
    cmd = AethyroCommand()
    task = cmd.assign_web_engineer_task(gid, "seo_audit")
    assert task["site_agent"] == "seo"
    assert task["domain"] == "aethyro.com"


def test_elite_lineage_web_engineers():
    mgr = EliteLineageManager()
    pop = mgr.ensure_lineage("WEB_ENGINEER_ELITE")
    assert len(pop) >= 8
    stats = mgr.get_lineage_stats()
    assert stats["WEB_ENGINEER_ELITE"]["hq"] == "https://aethyro.com"


def test_site_readiness_assessment():
    cmd = AethyroCommand()
    report = cmd.assess_site_readiness(implemented_trust=["ssl_https"], monthly_visitors=100)
    assert report["domain"] == "aethyro.com"
    assert "trust" in report
    assert "revenue_plan" in report
    assert "seo" in report["site_agent_bridge"]