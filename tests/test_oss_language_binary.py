"""Tests for the OSS language binary-coding layer."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.language.vocab_clusters import VocabClusters, VocabClusterConfig
from oss.language.semantic_codes import SemanticCodecs, SemanticCodeConfig
from oss.language.conversation_modes import ConversationModes, ModeConfig
from oss.language.genome_linguistics import (
    LinguisticTraits, genome_to_linguistic_traits, dominant_mode,
)
from oss.language.ors_embeddings import ORSEmbeddings, ORSEmbeddingConfig
from oss.living_loop.genome import KernelGenome


# ── VocabClusters ─────────────────────────────────────────────────────────────

def test_vocab_clusters_assign_binary_codes():
    embeddings = np.random.default_rng(0).standard_normal((128, 32)).astype(np.float32)
    vc = VocabClusters(embeddings, VocabClusterConfig(n_clusters=8, code_bits=4))
    vc.fit_clusters()
    code = vc.code_for_token(0)
    assert code.shape == (4,)
    assert set(np.unique(code)).issubset({0.0, 1.0})
    assert "balance_std" in vc.telemetry


def test_vocab_clusters_all_tokens_get_codes():
    V, D = 64, 32
    emb = np.random.default_rng(1).standard_normal((V, D)).astype(np.float32)
    vc = VocabClusters(emb, VocabClusterConfig(n_clusters=4, code_bits=4))
    vc.fit_clusters()
    assert len(vc.codes) == V


def test_vocab_clusters_missing_token_returns_zeros():
    emb = np.random.default_rng(2).standard_normal((16, 32)).astype(np.float32)
    vc = VocabClusters(emb, VocabClusterConfig(n_clusters=4, code_bits=6))
    vc.fit_clusters()
    code = vc.code_for_token(9999)
    assert np.all(code == 0.0)
    assert code.shape == (6,)


def test_vocab_clusters_encode_sequence():
    emb = np.random.default_rng(3).standard_normal((32, 32)).astype(np.float32)
    vc = VocabClusters(emb, VocabClusterConfig(n_clusters=4, code_bits=4))
    vc.fit_clusters()
    token_ids = np.array([[0, 1, 2], [3, 4, 5]])
    codes = vc.encode_sequence(token_ids)
    assert codes.shape == (2, 3, 4)
    assert set(np.unique(codes)).issubset({0.0, 1.0})


def test_vocab_clusters_telemetry_keys():
    emb = np.random.default_rng(4).standard_normal((32, 16)).astype(np.float32)
    vc = VocabClusters(emb, VocabClusterConfig(n_clusters=4, code_bits=4))
    vc.fit_clusters()
    assert "n_clusters_used" in vc.telemetry
    assert "balance_std" in vc.telemetry
    assert "mean_tokens_per_cluster" in vc.telemetry


def test_vocab_cluster_codes_are_unique_per_cluster():
    emb = np.random.default_rng(5).standard_normal((256, 32)).astype(np.float32)
    vc = VocabClusters(emb, VocabClusterConfig(n_clusters=8, code_bits=8))
    vc.fit_clusters()
    # Each cluster ID should map to a unique code
    seen_codes: set[tuple] = set()
    assert vc.cluster_ids is not None
    for cid in np.unique(vc.cluster_ids):
        token_id = int(np.where(vc.cluster_ids == cid)[0][0])
        code_tuple = tuple(vc.code_for_token(token_id).tolist())
        seen_codes.add(code_tuple)
    assert len(seen_codes) == len(np.unique(vc.cluster_ids))


# ── SemanticCodecs ────────────────────────────────────────────────────────────

def test_semantic_codes_roundtrip():
    cfg = SemanticCodeConfig(feature_dim=8, code_bits=4)
    sc = SemanticCodecs(cfg)
    features = np.random.default_rng(10).standard_normal(8).astype(np.float32)
    code = sc.encode(features)
    recon = sc.decode(code)
    assert code.shape == (4,)
    assert recon.shape == (8,)
    assert set(np.unique(code)).issubset({0.0, 1.0})


def test_semantic_codes_binary_output():
    sc = SemanticCodecs(SemanticCodeConfig(feature_dim=16, code_bits=8))
    batch = np.random.default_rng(11).standard_normal((10, 16)).astype(np.float32)
    codes = sc.encode(batch)
    assert codes.shape == (10, 8)
    assert set(np.unique(codes)).issubset({0.0, 1.0})


def test_semantic_codes_reconstruction_error_is_float():
    sc = SemanticCodecs(SemanticCodeConfig(feature_dim=8, code_bits=4))
    f = np.ones(8, dtype=np.float32)
    err = sc.reconstruction_error(f)
    assert isinstance(err, float)
    assert err >= 0.0


def test_semantic_codes_set_weights():
    cfg = SemanticCodeConfig(feature_dim=4, code_bits=4)
    sc = SemanticCodecs(cfg)
    new_W = np.eye(4, dtype=np.float32)
    sc.set_weights(new_W)
    assert np.allclose(sc.encoder_W, new_W)
    assert np.allclose(sc.decoder_W, new_W.T)


# ── ConversationModes ─────────────────────────────────────────────────────────

def test_conversation_modes_provide_binary_codes():
    cm = ConversationModes(ModeConfig(code_bits=8))
    code = cm.code_for_mode("technical")
    assert code.ndim == 1
    assert code.shape == (8,)
    assert set(np.unique(code)).issubset({0.0, 1.0})


def test_conversation_modes_register_custom():
    cm = ConversationModes(ModeConfig(code_bits=8))
    cm.register_mode("custom", np.ones(8, dtype=np.float32))
    custom = cm.code_for_mode("custom")
    assert custom.shape == (8,)
    assert np.all(custom == 1.0)


def test_conversation_modes_unknown_returns_zeros():
    cm = ConversationModes(ModeConfig(code_bits=8))
    code = cm.code_for_mode("nonexistent_mode")
    assert np.all(code == 0.0)


def test_conversation_modes_inject_into_sequence():
    cm = ConversationModes(ModeConfig(code_bits=4))
    x = np.zeros((2, 3, 16), dtype=np.float32)
    out = cm.inject_into_sequence(x, "technical")
    assert out.shape == (2, 3, 20)   # 16 + 4


def test_conversation_modes_list_modes():
    cm = ConversationModes()
    modes = cm.list_modes()
    assert "technical" in modes
    assert "exploratory" in modes
    assert "loyal_stable" in modes
    assert "innovative" in modes


def test_conversation_modes_different_modes_differ():
    cm = ConversationModes(ModeConfig(code_bits=8))
    tech = cm.code_for_mode("technical")
    expl = cm.code_for_mode("exploratory")
    assert not np.array_equal(tech, expl)


# ── GenomeLinguistics ─────────────────────────────────────────────────────────

def test_genome_linguistics_mapping():
    g = KernelGenome(genome_id="g1", temperature=1.0, max_growth=0.5, training_binary_ratio=0.9)
    traits = genome_to_linguistic_traits(g)
    assert 0.0 <= traits.loyalty_bias <= 1.0
    assert 0.0 <= traits.technical_bias <= 1.0
    assert 0.0 <= traits.casual_bias <= 1.0
    assert 0.0 <= traits.precision_bias <= 1.0
    assert 0.0 <= traits.innovation_bias <= 1.0


def test_genome_linguistics_technical_bias_low_temperature():
    # Low temperature → high technical bias
    g_cold = KernelGenome(genome_id="cold", temperature=0.2)
    g_warm = KernelGenome(genome_id="warm", temperature=8.0)
    t_cold = genome_to_linguistic_traits(g_cold)
    t_warm = genome_to_linguistic_traits(g_warm)
    assert t_cold.technical_bias > t_warm.technical_bias


def test_genome_linguistics_loyalty_from_tbr():
    g = KernelGenome(genome_id="loyal", training_binary_ratio=0.95)
    traits = genome_to_linguistic_traits(g)
    assert traits.loyalty_bias == pytest.approx(0.95)


def test_dominant_mode_returns_valid_mode():
    g = KernelGenome(genome_id="dom", temperature=1.0, max_growth=0.5, training_binary_ratio=0.8)
    traits = genome_to_linguistic_traits(g)
    mode = dominant_mode(traits)
    assert mode in ("technical", "exploratory", "loyal_stable", "innovative")


def test_dominant_mode_loyal_genome():
    # High loyalty + precision → "loyal_stable"
    traits = LinguisticTraits(
        loyalty_bias=0.95, precision_bias=0.9,
        technical_bias=0.1, casual_bias=0.1,
        innovation_bias=0.05,
    )
    assert dominant_mode(traits) == "loyal_stable"


def test_dominant_mode_innovative_genome():
    # High innovation + low loyalty → "innovative"
    traits = LinguisticTraits(
        innovation_bias=0.95, loyalty_bias=0.05,
        technical_bias=0.1, casual_bias=0.5, precision_bias=0.1,
    )
    assert dominant_mode(traits) == "innovative"


# ── ORSEmbeddings ─────────────────────────────────────────────────────────────

def test_ors_embeddings_rotates_per_head():
    base = np.random.default_rng(20).standard_normal((64, 32)).astype(np.float32)
    g = KernelGenome(genome_id="ors-g1")
    oe = ORSEmbeddings(base, ORSEmbeddingConfig(num_heads=4, embed_dim=32))
    oe.build_for_genome(g)
    head0 = oe.head_embeddings(0)
    head1 = oe.head_embeddings(1)
    assert head0.shape == (64, 8)
    assert head1.shape == (64, 8)
    assert not np.allclose(head0, head1)


def test_ors_embeddings_all_heads_concatenated_shape():
    base = np.random.default_rng(21).standard_normal((32, 32)).astype(np.float32)
    g = KernelGenome(genome_id="ors-g2")
    oe = ORSEmbeddings(base, ORSEmbeddingConfig(num_heads=4, embed_dim=32))
    oe.build_for_genome(g)
    full = oe.all_heads_concatenated()
    assert full.shape == (32, 32)


def test_ors_embeddings_identity_variant_close_to_original():
    base = np.random.default_rng(22).standard_normal((16, 32)).astype(np.float32)
    g = KernelGenome(genome_id="ors-id", ors_variant="identity")
    oe = ORSEmbeddings(base, ORSEmbeddingConfig(num_heads=4, embed_dim=32))
    oe.build_for_genome(g)
    h0 = oe.head_embeddings(0)
    # Identity ORS: rotation is I, so head0 == base[:, 0:8]
    assert np.allclose(h0, base[:, :8], atol=1e-5)


def test_ors_embeddings_different_ors_variants_differ():
    base = np.random.default_rng(23).standard_normal((32, 32)).astype(np.float32)
    g_qr     = KernelGenome(genome_id="qr",     ors_variant="qr")
    g_random = KernelGenome(genome_id="random", ors_variant="random")
    oe_qr     = ORSEmbeddings(base, ORSEmbeddingConfig(num_heads=4, embed_dim=32))
    oe_random = ORSEmbeddings(base, ORSEmbeddingConfig(num_heads=4, embed_dim=32))
    oe_qr.build_for_genome(g_qr)
    oe_random.build_for_genome(g_random)
    assert not np.allclose(oe_qr.head_embeddings(0), oe_random.head_embeddings(0))


def test_ors_embeddings_unbuilt_head_fallback():
    base = np.random.default_rng(24).standard_normal((16, 32)).astype(np.float32)
    oe = ORSEmbeddings(base, ORSEmbeddingConfig(num_heads=4, embed_dim=32))
    # build_for_genome not called — should fall back to base slice
    h2 = oe.head_embeddings(2)
    assert h2.shape == (16, 8)
    assert np.allclose(h2, base[:, 16:24])
