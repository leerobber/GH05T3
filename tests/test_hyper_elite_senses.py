"""
tests/test_hyper_elite_senses.py

Full coverage for backend/oss/hyper_elite/senses.py

Tests:
- HyperEliteSenses dataclass init and calibration defaults
- attach_hyper_elite_senses wires trait → calibration correctly
- scan() produces exactly 8 readings with correct sense names
- Each sense has intensity in [0, 1]
- profit_pulse baseline always >= 0.85 (survival mandate)
- domain_radar fires on novel terms
- swarm_resonance high when swarm_id present
- to_prompt_block() contains tier and sense names
- snapshot() has required keys
- is_elite_role() helper
- Integration: OmniDNA elite role auto-attaches senses
"""

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import pytest
from backend.oss.hyper_elite.senses import (
    HyperEliteSenses,
    SenseReading,
    attach_hyper_elite_senses,
    is_elite_role,
    HYPER_ELITE_SENSE_NAMES,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def base_senses():
    return HyperEliteSenses(genome_id="test-genome-001", tier="T2")


@pytest.fixture
def elite_context():
    return {
        "prompt": "find arbitrage profit in DeFi yield farming",
        "world": "volatility",
        "fitness": 0.85,
        "swarm_id": "swarm-42",
    }


@pytest.fixture
def minimal_context():
    return {"prompt": "simple query", "fitness": 0.4}


# ──────────────────────────────────────────────────────────────────────────────
# 1. Dataclass init
# ──────────────────────────────────────────────────────────────────────────────

class TestInit:
    def test_genome_id_stored(self, base_senses):
        assert base_senses.genome_id == "test-genome-001"

    def test_tier_stored(self, base_senses):
        assert base_senses.tier == "T2"

    def test_calibration_has_all_senses(self, base_senses):
        for name in HYPER_ELITE_SENSE_NAMES:
            assert name in base_senses.calibration, f"Missing: {name}"

    def test_calibration_defaults_are_0_75(self, base_senses):
        for name in HYPER_ELITE_SENSE_NAMES:
            assert base_senses.calibration[name] == 0.75

    def test_last_readings_empty_on_init(self, base_senses):
        assert base_senses.last_readings == []


# ──────────────────────────────────────────────────────────────────────────────
# 2. attach_hyper_elite_senses
# ──────────────────────────────────────────────────────────────────────────────

class TestAttach:
    def test_attach_returns_hyper_elite_senses(self):
        from backend.oss.omni_dna import OmniDNA
        dna = OmniDNA("attach-test-001", role="THEORIST_ELITE")
        senses = attach_hyper_elite_senses(dna, tier="T2")
        assert isinstance(senses, HyperEliteSenses)

    def test_attach_genome_id_matches(self):
        from backend.oss.omni_dna import OmniDNA
        dna = OmniDNA("attach-test-002", role="ARCHITECT_ELITE")
        senses = attach_hyper_elite_senses(dna, tier="T3")
        assert senses.genome_id == dna.genome_id

    def test_attach_tier_set(self):
        from backend.oss.omni_dna import OmniDNA
        dna = OmniDNA("attach-test-003", role="ARCHITECT_ELITE")
        senses = attach_hyper_elite_senses(dna, tier="T3")
        assert senses.tier == "T3"

    def test_vision_spectrum_derived_from_pattern_detection(self):
        from backend.oss.omni_dna import OmniDNA
        dna = OmniDNA("attach-test-004", role="THEORIST_ELITE",
                      traits={t: 0.5 for t in ["novelty_seeking","rigor","risk_tolerance",
                              "persistence","creativity","efficiency","collaboration",
                              "math","pattern_detection","self_reflection","alignment",
                              "innovation","market_intuition","empathy"]})
        dna.traits["pattern_detection"] = 0.70
        senses = attach_hyper_elite_senses(dna)
        expected = min(0.95, 0.70 + 0.20)
        assert abs(senses.calibration["vision_spectrum"] - expected) < 0.001

    def test_profit_pulse_derived_from_market_intuition(self):
        from backend.oss.omni_dna import OmniDNA
        dna = OmniDNA("attach-test-005", role="WEB_ENGINEER_ELITE",
                      traits={t: 0.5 for t in ["novelty_seeking","rigor","risk_tolerance",
                              "persistence","creativity","efficiency","collaboration",
                              "math","pattern_detection","self_reflection","alignment",
                              "innovation","market_intuition","empathy"]})
        dna.traits["market_intuition"] = 0.65
        senses = attach_hyper_elite_senses(dna)
        expected = min(0.95, 0.65 + 0.20)
        assert abs(senses.calibration["profit_pulse"] - expected) < 0.001


# ──────────────────────────────────────────────────────────────────────────────
# 3. scan() — core sense outputs
# ──────────────────────────────────────────────────────────────────────────────

class TestScan:
    def test_scan_returns_8_readings(self, base_senses, elite_context):
        readings = base_senses.scan(elite_context)
        assert len(readings) == 8

    def test_scan_all_sense_names_present(self, base_senses, elite_context):
        readings = base_senses.scan(elite_context)
        names = {r.sense for r in readings}
        for expected in HYPER_ELITE_SENSE_NAMES:
            assert expected in names, f"Missing sense: {expected}"

    def test_scan_intensities_in_range(self, base_senses, elite_context):
        for r in base_senses.scan(elite_context):
            assert 0.0 <= r.intensity <= 1.0, f"{r.sense} intensity={r.intensity} out of range"

    def test_scan_returns_sense_reading_objects(self, base_senses, minimal_context):
        for r in base_senses.scan(minimal_context):
            assert isinstance(r, SenseReading)

    def test_last_readings_updated_after_scan(self, base_senses, elite_context):
        assert len(base_senses.last_readings) == 0
        base_senses.scan(elite_context)
        assert len(base_senses.last_readings) == 8

    def test_last_readings_bounded_at_20(self, base_senses, elite_context):
        for _ in range(5):
            base_senses.scan(elite_context)
        assert len(base_senses.last_readings) <= 20


# ──────────────────────────────────────────────────────────────────────────────
# 4. profit_pulse survival mandate
# ──────────────────────────────────────────────────────────────────────────────

class TestProfitPulse:
    def _get_reading(self, senses, context, sense_name):
        return next(r for r in senses.scan(context) if r.sense == sense_name)

    def test_profit_pulse_baseline_always_ge_085(self, base_senses):
        ctx = {"prompt": "simple task with no money terms", "fitness": 0.2}
        r = self._get_reading(base_senses, ctx, "profit_pulse")
        assert r.intensity >= 0.85, f"profit_pulse baseline={r.intensity} < 0.85 (survival mandate violated)"

    def test_profit_pulse_higher_with_money_terms(self, base_senses):
        ctx_no = {"prompt": "analyze data", "fitness": 0.5}
        ctx_yes = {"prompt": "maximize profit revenue monetize income", "fitness": 0.5}
        r_no = self._get_reading(base_senses, ctx_no, "profit_pulse")
        r_yes = self._get_reading(base_senses, ctx_yes, "profit_pulse")
        assert r_yes.intensity >= r_no.intensity

    def test_profit_pulse_survival_critical_signal(self, base_senses):
        ctx = {"prompt": "find crypto yield arbitrage profit", "fitness": 0.7}
        r = self._get_reading(base_senses, ctx, "profit_pulse")
        assert "survival_critical" in r.signal


# ──────────────────────────────────────────────────────────────────────────────
# 5. domain_radar
# ──────────────────────────────────────────────────────────────────────────────

class TestDomainRadar:
    def _get_reading(self, senses, context):
        return next(r for r in senses.scan(context) if r.sense == "domain_radar")

    def test_novel_terms_increase_domain_radar(self, base_senses):
        ctx_plain = {"prompt": "calculate totals", "fitness": 0.5}
        ctx_novel = {"prompt": "unknown fractal dimension in novel DeFi regime", "fitness": 0.5}
        r_plain = self._get_reading(base_senses, ctx_plain)
        r_novel = self._get_reading(base_senses, ctx_novel)
        assert r_novel.intensity > r_plain.intensity

    def test_new_domain_signal_on_high_novelty(self, base_senses):
        ctx = {"prompt": "unknown novel fractal regime dimension", "fitness": 0.5}
        r = self._get_reading(base_senses, ctx)
        assert r.signal == "new_domain_detected"


# ──────────────────────────────────────────────────────────────────────────────
# 6. swarm_resonance
# ──────────────────────────────────────────────────────────────────────────────

class TestSwarmResonance:
    def _get_reading(self, senses, context):
        return next(r for r in senses.scan(context) if r.sense == "swarm_resonance")

    def test_high_resonance_with_swarm_id(self, base_senses):
        ctx = {"prompt": "task", "fitness": 0.5, "swarm_id": "swarm-001"}
        r = self._get_reading(base_senses, ctx)
        assert r.intensity >= 0.80

    def test_low_resonance_without_swarm_id(self, base_senses):
        ctx = {"prompt": "solo task", "fitness": 0.5}
        r = self._get_reading(base_senses, ctx)
        assert r.intensity < 0.60

    def test_collective_lock_signal_with_swarm(self, base_senses):
        ctx = {"prompt": "task", "fitness": 0.5, "swarm_id": "swarm-XYZ"}
        r = self._get_reading(base_senses, ctx)
        assert r.signal == "collective_lock"


# ──────────────────────────────────────────────────────────────────────────────
# 7. to_prompt_block
# ──────────────────────────────────────────────────────────────────────────────

class TestPromptBlock:
    def test_prompt_block_contains_tier(self, base_senses):
        block = base_senses.to_prompt_block()
        assert "T2" in block

    def test_prompt_block_contains_sense_names(self, base_senses):
        block = base_senses.to_prompt_block()
        for name in HYPER_ELITE_SENSE_NAMES:
            assert name in block, f"Missing sense in prompt block: {name}"

    def test_prompt_block_dominant_signal_after_scan(self, base_senses, elite_context):
        base_senses.scan(elite_context)
        block = base_senses.to_prompt_block()
        assert "Dominant signal" in block

    def test_prompt_block_is_string(self, base_senses):
        assert isinstance(base_senses.to_prompt_block(), str)


# ──────────────────────────────────────────────────────────────────────────────
# 8. snapshot
# ──────────────────────────────────────────────────────────────────────────────

class TestSnapshot:
    def test_snapshot_has_required_keys(self, base_senses, elite_context):
        base_senses.scan(elite_context)
        snap = base_senses.snapshot()
        for key in ("genome_id", "tier", "calibration", "last_readings"):
            assert key in snap, f"Missing key: {key}"

    def test_snapshot_genome_id_correct(self, base_senses, elite_context):
        base_senses.scan(elite_context)
        snap = base_senses.snapshot()
        assert snap["genome_id"] == "test-genome-001"

    def test_snapshot_last_readings_bounded(self, base_senses, elite_context):
        for _ in range(3):
            base_senses.scan(elite_context)
        snap = base_senses.snapshot()
        assert len(snap["last_readings"]) <= 8


# ──────────────────────────────────────────────────────────────────────────────
# 9. is_elite_role helper
# ──────────────────────────────────────────────────────────────────────────────

class TestIsEliteRole:
    def test_elite_suffix_detected(self):
        assert is_elite_role("THEORIST_ELITE") is True

    def test_elite_in_name_detected(self):
        assert is_elite_role("SUPER_ELITE_AGENT") is True

    def test_t2_tier_is_elite(self):
        assert is_elite_role("SCIENTIST", tier="T2") is True

    def test_t0_non_elite_role_is_false(self):
        assert is_elite_role("SCIENTIST", tier="T0") is False

    def test_plain_role_is_false(self):
        assert is_elite_role("OPERATOR") is False

    def test_empty_role_is_false(self):
        assert is_elite_role("") is False


# ──────────────────────────────────────────────────────────────────────────────
# 10. Integration — OmniDNA elite auto-attach
# ──────────────────────────────────────────────────────────────────────────────

class TestOmniDNAIntegration:
    def test_elite_dna_has_senses_attached(self):
        from backend.oss.omni_dna import OmniDNA
        dna = OmniDNA("integ-001", role="THEORIST_ELITE")
        assert dna.hyper_elite_senses is not None

    def test_elite_dna_power_tier_is_t2(self):
        from backend.oss.omni_dna import OmniDNA
        dna = OmniDNA("integ-002", role="ARCHITECT_ELITE")
        assert dna.power_tier == "T2"

    def test_non_elite_dna_has_no_senses(self):
        from backend.oss.omni_dna import OmniDNA
        dna = OmniDNA("integ-003", role="SCIENTIST")
        assert dna.hyper_elite_senses is None

    def test_scan_senses_via_dna_api(self):
        from backend.oss.omni_dna import OmniDNA
        dna = OmniDNA("integ-004", role="WEB_ENGINEER_ELITE")
        results = dna.scan_senses({"prompt": "build revenue funnel", "fitness": 0.8})
        assert len(results) == 8
        for r in results:
            assert "sense" in r
            assert "intensity" in r
