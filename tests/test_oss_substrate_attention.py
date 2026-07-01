"""Tests for substrate-level AttentionConfig integration and AttentionDomainScorer."""
from __future__ import annotations

import numpy as np
import pytest

from oss.substrate.attention_config import (
    CANONICAL_TRAITS,
    TRAIT_DIM,
    AttentionConfig,
    traits_to_vector,
)


# ── CANONICAL_TRAITS ──────────────────────────────────────────────────────────

def test_canonical_traits_length():
    assert len(CANONICAL_TRAITS) == 32


def test_trait_dim_matches():
    assert TRAIT_DIM == 32


def test_canonical_traits_unique():
    assert len(set(CANONICAL_TRAITS)) == len(CANONICAL_TRAITS)


def test_canonical_traits_are_strings():
    assert all(isinstance(t, str) for t in CANONICAL_TRAITS)


# ── traits_to_vector ──────────────────────────────────────────────────────────

def test_traits_to_vector_shape():
    vec = traits_to_vector({})
    assert vec.shape == (32,)
    assert vec.dtype == np.float32


def test_traits_to_vector_default_neutral():
    vec = traits_to_vector({})
    np.testing.assert_allclose(vec, 0.5, atol=1e-6)


def test_traits_to_vector_known_value():
    vec = traits_to_vector({"coding": 0.9, "math": 0.1})
    idx_coding = CANONICAL_TRAITS.index("coding")
    idx_math = CANONICAL_TRAITS.index("math")
    assert abs(vec[idx_coding] - 0.9) < 1e-5
    assert abs(vec[idx_math] - 0.1) < 1e-5


def test_traits_to_vector_clips_range():
    vec = traits_to_vector({"coding": 1.5, "math": -0.3})
    assert 0.0 <= float(vec[CANONICAL_TRAITS.index("coding")]) <= 1.0
    assert 0.0 <= float(vec[CANONICAL_TRAITS.index("math")]) <= 1.0


def test_traits_to_vector_unknown_key_ignored():
    vec = traits_to_vector({"nonexistent_trait_xyz": 0.99})
    np.testing.assert_allclose(vec, 0.5, atol=1e-6)


# ── AttentionConfig defaults ───────────────────────────────────────────────────

def test_attention_config_defaults():
    cfg = AttentionConfig()
    assert cfg.embed_dim == 32
    assert cfg.num_heads == 4
    assert cfg.binary_ratio == 0.0
    assert cfg.training_binary_ratio == 1.0
    assert cfg.temperature == 1.0
    assert cfg.max_growth == 0.5
    assert cfg.seed == 0


def test_attention_config_default_factory():
    cfg = AttentionConfig.default()
    assert isinstance(cfg, AttentionConfig)
    assert cfg.embed_dim == 32


# ── AttentionConfig.from_genome_traits ────────────────────────────────────────

def test_from_genome_traits_temperature_derivation():
    traits = {"analysis": 0.8}
    cfg = AttentionConfig.from_genome_traits(traits)
    expected_temp = max(0.2, 1.0 - 0.6 * 0.8)
    assert abs(cfg.temperature - round(expected_temp, 4)) < 1e-4


def test_from_genome_traits_max_growth_derivation():
    traits = {"risk_tolerance": 0.6}
    cfg = AttentionConfig.from_genome_traits(traits)
    expected_mg = 0.2 + 0.6 * 0.6
    assert abs(cfg.max_growth - round(expected_mg, 4)) < 1e-4


def test_from_genome_traits_training_binary_ratio_derivation():
    traits = {"reliability": 0.9}
    cfg = AttentionConfig.from_genome_traits(traits)
    expected_tbr = 0.7 + 0.3 * 0.9
    assert abs(cfg.training_binary_ratio - round(expected_tbr, 4)) < 1e-4


def test_from_genome_traits_temperature_floor():
    traits = {"analysis": 1.0}
    cfg = AttentionConfig.from_genome_traits(traits)
    assert cfg.temperature >= 0.2


def test_from_genome_traits_seed_deterministic():
    cfg1 = AttentionConfig.from_genome_traits({}, genome_id="test-genome-abc")
    cfg2 = AttentionConfig.from_genome_traits({}, genome_id="test-genome-abc")
    assert cfg1.seed == cfg2.seed


def test_from_genome_traits_seed_varies_by_id():
    cfg1 = AttentionConfig.from_genome_traits({}, genome_id="genome-aaa")
    cfg2 = AttentionConfig.from_genome_traits({}, genome_id="genome-bbb")
    assert cfg1.seed != cfg2.seed


def test_from_genome_traits_no_id_seed_zero():
    cfg = AttentionConfig.from_genome_traits({}, genome_id="")
    assert cfg.seed == 0


def test_from_genome_traits_default_traits():
    cfg = AttentionConfig.from_genome_traits({})
    assert cfg.temperature == round(max(0.2, 1.0 - 0.6 * 0.5), 4)
    assert cfg.max_growth == round(0.2 + 0.6 * 0.5, 4)
    assert cfg.training_binary_ratio == round(0.7 + 0.3 * 0.5, 4)


# ── AttentionConfig serialisation ─────────────────────────────────────────────

def test_attention_config_roundtrip():
    cfg = AttentionConfig(embed_dim=32, num_heads=4, temperature=0.7, max_growth=0.4, seed=12345)
    d = cfg.to_dict()
    cfg2 = AttentionConfig.from_dict(d)
    assert cfg.temperature == cfg2.temperature
    assert cfg.max_growth == cfg2.max_growth
    assert cfg.seed == cfg2.seed


def test_attention_config_to_dict_keys():
    d = AttentionConfig().to_dict()
    for key in ("embed_dim", "num_heads", "binary_ratio", "training_binary_ratio",
                "temperature", "max_growth", "seed"):
        assert key in d


def test_attention_config_from_dict_defaults():
    cfg = AttentionConfig.from_dict({})
    assert cfg.embed_dim == 32
    assert cfg.num_heads == 4


# ── AttentionConfig.build_module ──────────────────────────────────────────────

def test_build_module_returns_attention():
    from oss.attention.attention import MA_INBLAttention
    cfg = AttentionConfig()
    module = cfg.build_module()
    assert isinstance(module, MA_INBLAttention)


def test_build_module_forward_shape():
    cfg = AttentionConfig(embed_dim=32, num_heads=4)
    module = cfg.build_module()
    x = np.random.randn(5, 32).astype(np.float32)
    out, tel = module.forward(x)
    assert out.shape == (5, 32)


def test_build_module_uses_config_temperature():
    cfg = AttentionConfig(temperature=0.3)
    module = cfg.build_module()
    assert module.temperature == pytest.approx(0.3, abs=1e-6)


# ── GenomicSubstrate integration ──────────────────────────────────────────────

def test_substrate_segment_has_attention_config():
    from oss.substrate.genomic import GenomicSubstrate
    from oss.dna.omni_dna import OmniDNA
    sub = GenomicSubstrate()
    genome_id = "test-genome-attn-001"
    dna = OmniDNA(genome_id=genome_id)
    sub.register_genome(dna)
    seg = sub.segment(genome_id)
    assert seg is not None
    assert seg.attention_config is not None
    assert isinstance(seg.attention_config, AttentionConfig)


def test_substrate_segment_attention_config_embed_dim():
    from oss.substrate.genomic import GenomicSubstrate
    from oss.dna.omni_dna import OmniDNA
    sub = GenomicSubstrate()
    genome_id = "test-genome-attn-002"
    dna = OmniDNA(genome_id=genome_id)
    sub.register_genome(dna)
    seg = sub.segment(genome_id)
    assert seg.attention_config.embed_dim == 32


def test_substrate_get_attention_module():
    from oss.attention.attention import MA_INBLAttention
    from oss.substrate.genomic import GenomicSubstrate
    from oss.dna.omni_dna import OmniDNA
    sub = GenomicSubstrate()
    genome_id = "test-genome-attn-003"
    dna = OmniDNA(genome_id=genome_id)
    sub.register_genome(dna)
    module = sub.get_attention_module(genome_id)
    assert isinstance(module, MA_INBLAttention)


def test_substrate_get_attention_module_missing_raises():
    from oss.substrate.genomic import GenomicSubstrate
    sub = GenomicSubstrate()
    with pytest.raises(KeyError):
        sub.get_attention_module("nonexistent-genome-xyz")


def test_substrate_get_attention_module_forward():
    from oss.substrate.genomic import GenomicSubstrate
    from oss.dna.omni_dna import OmniDNA
    sub = GenomicSubstrate()
    genome_id = "test-genome-attn-004"
    dna = OmniDNA(genome_id=genome_id)
    sub.register_genome(dna)
    module = sub.get_attention_module(genome_id)
    x = np.random.randn(3, 32).astype(np.float32)
    out, tel = module.forward(x)
    assert out.shape == (3, 32)


# ── AttentionDomainScorer ─────────────────────────────────────────────────────

def test_domain_scorer_score_length():
    from oss.forge.attention_scorer import AttentionDomainScorer
    scorer = AttentionDomainScorer()
    traits = [{"coding": 0.9, "math": 0.8}, {"analysis": 0.7}, {"research": 0.6}]
    scores = scorer.score("deep_learning_architectures", traits, log_telemetry=False)
    assert len(scores) == 3


def test_domain_scorer_scores_in_range():
    from oss.forge.attention_scorer import AttentionDomainScorer
    scorer = AttentionDomainScorer()
    traits = [{"coding": 0.9}, {"math": 0.5}, {"general": 0.3}]
    scores = scorer.score("machine_learning_theory", traits, log_telemetry=False)
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_domain_scorer_empty_returns_empty():
    from oss.forge.attention_scorer import AttentionDomainScorer
    scorer = AttentionDomainScorer()
    assert scorer.score("general_cognition", [], log_telemetry=False) == []


def test_domain_scorer_rank_indices():
    from oss.forge.attention_scorer import AttentionDomainScorer
    scorer = AttentionDomainScorer()
    traits = [{"math": 0.9, "research": 0.9}, {"coding": 0.2}, {"analysis": 0.5}]
    indices = scorer.rank("machine_learning_theory", traits)
    assert sorted(indices) == [0, 1, 2]
    assert len(indices) == 3


def test_domain_scorer_rank_descending():
    from oss.forge.attention_scorer import AttentionDomainScorer
    scorer = AttentionDomainScorer()
    traits = [{"math": 0.9, "research": 0.9}, {"coding": 0.2}, {"analysis": 0.5}]
    indices = scorer.rank("machine_learning_theory", traits)
    scores = scorer.score("machine_learning_theory", traits, log_telemetry=False)
    for i in range(len(indices) - 1):
        assert scores[indices[i]] >= scores[indices[i + 1]]


def test_domain_scorer_with_fitness():
    from oss.forge.attention_scorer import AttentionDomainScorer
    scorer = AttentionDomainScorer()
    traits = [{"coding": 0.9}, {"coding": 0.1}]
    fitness = [0.9, 0.1]
    scores = scorer.score("agentic_systems_science", traits, fitness, log_telemetry=False)
    assert len(scores) == 2
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_domain_scorer_unknown_domain_falls_back():
    from oss.forge.attention_scorer import AttentionDomainScorer
    scorer = AttentionDomainScorer()
    traits = [{"general": 0.8}]
    scores = scorer.score("totally_unknown_domain_xyz", traits, log_telemetry=False)
    assert len(scores) == 1
    assert 0.0 <= scores[0] <= 1.0


def test_domain_trait_vector_shape():
    from oss.forge.attention_scorer import domain_trait_vector
    vec = domain_trait_vector("markets")
    assert vec.shape == (32,)


def test_domain_trait_vector_unknown_fallback():
    from oss.forge.attention_scorer import domain_trait_vector
    vec1 = domain_trait_vector("unknown_xyz")
    vec2 = domain_trait_vector("general_cognition")
    np.testing.assert_array_equal(vec1, vec2)


# ── score_strands_for_domain ──────────────────────────────────────────────────

def test_score_strands_for_domain_sorted_descending():
    from oss.forge.attention_scorer import score_strands_for_domain
    strands = [
        {"traits": {"math": 0.9, "research": 0.9}, "fitness": 0.9},
        {"traits": {"coding": 0.2}, "fitness": 0.2},
        {"traits": {"analysis": 0.6}, "fitness": 0.5},
    ]
    ranked = score_strands_for_domain("machine_learning_theory", strands)
    assert len(ranked) == 3
    scores = [r[0] for r in ranked]
    assert scores == sorted(scores, reverse=True)


def test_score_strands_for_domain_returns_tuples():
    from oss.forge.attention_scorer import score_strands_for_domain
    strands = [{"traits": {"coding": 0.8}, "fitness": 0.7}]
    ranked = score_strands_for_domain("agentic_systems_science", strands)
    assert isinstance(ranked[0], tuple)
    assert isinstance(ranked[0][0], float)
    assert isinstance(ranked[0][1], dict)


def test_score_strands_empty():
    from oss.forge.attention_scorer import score_strands_for_domain
    ranked = score_strands_for_domain("markets", [])
    assert ranked == []


def test_score_strands_missing_traits_key():
    from oss.forge.attention_scorer import score_strands_for_domain
    strands = [{"fitness": 0.5}, {"traits": None, "fitness": 0.3}]
    ranked = score_strands_for_domain("general_cognition", strands)
    assert len(ranked) == 2


# ── SubstrateBlock ────────────────────────────────────────────────────────────

def test_substrate_block_forward_shape():
    from oss.substrate.blocks import BlockConfig, SubstrateBlock
    cfg = BlockConfig(embed_dim=32, num_heads=4)
    block = SubstrateBlock(cfg)
    x = np.random.randn(5, 32).astype(np.float32)
    out, tel = block.forward(x)
    assert out.shape == (5, 32)


def test_substrate_block_forward_batch():
    from oss.substrate.blocks import BlockConfig, SubstrateBlock
    cfg = BlockConfig(embed_dim=32, num_heads=4)
    block = SubstrateBlock(cfg)
    x = np.random.randn(2, 5, 32).astype(np.float32)
    out, tel = block.forward(x)
    assert out.shape == (2, 5, 32)


def test_substrate_block_telemetry_keys():
    from oss.substrate.blocks import BlockConfig, SubstrateBlock
    cfg = BlockConfig(embed_dim=32, num_heads=4)
    block = SubstrateBlock(cfg)
    x = np.random.randn(3, 32).astype(np.float32)
    _, tel = block.forward(x)
    assert isinstance(tel, dict)


def test_substrate_block_uses_ma_inbl_attention():
    from oss.attention.attention import MA_INBLAttention
    from oss.substrate.blocks import BlockConfig, SubstrateBlock
    cfg = BlockConfig(embed_dim=32, num_heads=4)
    block = SubstrateBlock(cfg)
    assert isinstance(block.attn, MA_INBLAttention)


# ── SubstrateModel ────────────────────────────────────────────────────────────

def test_substrate_model_forward_shape():
    from oss.substrate.model import SubstrateConfig, SubstrateModel
    cfg = SubstrateConfig(embed_dim=32, num_heads=4, num_layers=2)
    model = SubstrateModel(cfg)
    x = np.random.randn(4, 32).astype(np.float32)
    out, tel_list = model.forward(x)
    assert out.shape == (4, 32)
    assert len(tel_list) == 2


def test_substrate_model_num_layers():
    from oss.substrate.model import SubstrateConfig, SubstrateModel
    cfg = SubstrateConfig(num_layers=3)
    model = SubstrateModel(cfg)
    assert model.num_layers == 3
    assert len(model.blocks) == 3


def test_substrate_model_attention_modules():
    from oss.attention.attention import MA_INBLAttention
    from oss.substrate.model import SubstrateConfig, SubstrateModel
    cfg = SubstrateConfig(num_layers=2)
    model = SubstrateModel(cfg)
    modules = list(model.attention_modules())
    assert len(modules) == 2
    for idx, m in modules:
        assert isinstance(m, MA_INBLAttention)


def test_substrate_config_from_attention_config():
    from oss.substrate.model import SubstrateConfig
    attn_cfg = AttentionConfig(temperature=0.7, max_growth=0.4, seed=99)
    sub_cfg = SubstrateConfig.from_attention_config(attn_cfg, num_layers=3)
    assert sub_cfg.attn_temperature == pytest.approx(0.7, abs=1e-5)
    assert sub_cfg.attn_max_growth == pytest.approx(0.4, abs=1e-5)
    assert sub_cfg.attn_seed == 99
    assert sub_cfg.num_layers == 3


def test_substrate_config_roundtrip():
    from oss.substrate.model import SubstrateConfig
    cfg = SubstrateConfig(embed_dim=32, num_heads=4, num_layers=2, attn_temperature=0.6)
    d = cfg.to_dict()
    cfg2 = SubstrateConfig.from_dict(d)
    assert cfg.attn_temperature == cfg2.attn_temperature
    assert cfg.num_layers == cfg2.num_layers


# ── SubstrateTransformer ──────────────────────────────────────────────────────

def test_substrate_transformer_encode_shape():
    from oss.substrate.transformer import SubstrateTransformer
    t = SubstrateTransformer.from_genome_traits({"coding": 0.9, "math": 0.8})
    x = np.random.randn(6, 32).astype(np.float32)
    out, tel = t.encode(x)
    assert out.shape == (6, 32)
    assert len(tel) == 2  # default 2 layers


def test_substrate_transformer_from_attention_config():
    from oss.substrate.transformer import SubstrateTransformer
    attn_cfg = AttentionConfig(temperature=0.5)
    t = SubstrateTransformer.from_attention_config(attn_cfg, num_layers=1)
    assert t.num_layers == 1
    assert t.embed_dim == 32


def test_substrate_transformer_score_candidates():
    from oss.substrate.transformer import SubstrateTransformer
    t = SubstrateTransformer.from_genome_traits({})
    query = np.random.randn(32).astype(np.float32)
    cands = np.random.randn(4, 32).astype(np.float32)
    scores = t.score_candidates(query, cands)
    assert scores.shape == (4,)
    assert np.all((scores >= 0.0) & (scores <= 1.0))


def test_substrate_build_model():
    from oss.substrate.genomic import GenomicSubstrate
    from oss.substrate.transformer import SubstrateTransformer
    from oss.dna.omni_dna import OmniDNA
    sub = GenomicSubstrate()
    genome_id = "test-build-model-001"
    dna = OmniDNA(genome_id=genome_id)
    sub.register_genome(dna)
    model = sub.build_model(genome_id)
    assert isinstance(model, SubstrateTransformer)
    x = np.random.randn(3, 32).astype(np.float32)
    out, _ = model.encode(x)
    assert out.shape == (3, 32)


def test_substrate_build_model_missing_raises():
    from oss.substrate.genomic import GenomicSubstrate
    sub = GenomicSubstrate()
    with pytest.raises(KeyError):
        sub.build_model("nonexistent-genome-model-xyz")


# ── OmniStrand attention_config ───────────────────────────────────────────────

def test_omnistrand_has_attention_config():
    from oss.forge.genetics import transcribe_strand
    from oss.forge.schemas import ForgeDomain, QualityTier, TrainingShard
    shard = TrainingShard(
        shard_id="test-strand-attn-01",
        genome_id="test-genome-strand",
        domain=ForgeDomain.MACHINE_LEARNING_THEORY,
        system="You are GH05T3.",
        user="Explain attention.",
        assistant="Attention is...",
        source="test",
    )
    strand = transcribe_strand(shard, score=0.85, tier=QualityTier.GOLD)
    assert strand.attention_config is not None
    assert "embed_dim" in strand.attention_config


def test_omnistrand_to_dict_includes_attention_config():
    from oss.forge.genetics import transcribe_strand
    from oss.forge.schemas import ForgeDomain, QualityTier, TrainingShard
    shard = TrainingShard(
        shard_id="test-strand-attn-02",
        genome_id="",
        domain=ForgeDomain.GENERAL_COGNITION,
        system="You are GH05T3.",
        user="Hello.",
        assistant="Hello!",
        source="test",
    )
    strand = transcribe_strand(shard, score=0.7, tier=QualityTier.SILVER)
    d = strand.to_dict()
    assert "attention_config" in d
    assert d["attention_config"]["embed_dim"] == 32


# ── train_bridge attention_config export ─────────────────────────────────────

def test_train_bridge_attention_config_in_export(tmp_path, monkeypatch):
    """export_gold records must carry an attention_config dict."""
    from oss.forge import train_bridge
    from oss.forge.schemas import ForgeDomain, TrainingShard

    monkeypatch.setattr(train_bridge, "_EXPORT_DIR", tmp_path)
    monkeypatch.setattr(train_bridge, "_GOLD_FILE", tmp_path / "gold.jsonl")
    monkeypatch.setattr(train_bridge, "_MANIFEST", tmp_path / "manifest.json")

    shard = TrainingShard(
        shard_id="test-shard-1",
        genome_id="test-genome-bridge",
        domain=ForgeDomain.DEEP_LEARNING_ARCHITECTURES,
        system="You are GH05T3.",
        user="What is attention?",
        assistant="Attention is a mechanism...",
        source="test",
    )

    from unittest.mock import MagicMock
    fake_store = MagicMock()
    fake_store.list_shards.return_value = [shard]
    monkeypatch.setattr(train_bridge, "get_store", lambda: fake_store)

    result = train_bridge.export_gold()
    assert result["exported"] == 1

    import json as _json
    lines = (tmp_path / "gold.jsonl").read_text().strip().split("\n")
    record = _json.loads(lines[0])
    assert "attention_config" in record
    cfg_dict = record["attention_config"]
    assert "embed_dim" in cfg_dict
    assert cfg_dict["embed_dim"] == 32


def test_train_bridge_attention_config_has_expected_keys(tmp_path, monkeypatch):
    from oss.forge import train_bridge
    from oss.forge.schemas import ForgeDomain, TrainingShard

    monkeypatch.setattr(train_bridge, "_EXPORT_DIR", tmp_path)
    monkeypatch.setattr(train_bridge, "_GOLD_FILE", tmp_path / "gold.jsonl")
    monkeypatch.setattr(train_bridge, "_MANIFEST", tmp_path / "manifest.json")

    shard = TrainingShard(
        shard_id="test-shard-2",
        genome_id="",
        domain=ForgeDomain.GENERAL_COGNITION,
        system="You are GH05T3.",
        user="Hello?",
        assistant="Hello!",
        source="test",
    )
    from unittest.mock import MagicMock
    fake_store = MagicMock()
    fake_store.list_shards.return_value = [shard]
    monkeypatch.setattr(train_bridge, "get_store", lambda: fake_store)

    train_bridge.export_gold()
    import json as _json
    record = _json.loads((tmp_path / "gold.jsonl").read_text().strip())
    cfg = record["attention_config"]
    for key in ("embed_dim", "num_heads", "binary_ratio", "training_binary_ratio",
                "temperature", "max_growth", "seed"):
        assert key in cfg, f"missing key: {key}"
