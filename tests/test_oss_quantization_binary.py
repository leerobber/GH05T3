"""Tests for the OSS binary / ternary quantization layer."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.quantization.binary_quant import BinaryQuantConfig, BinaryQuantizer
from oss.living_loop.genome import KernelGenome
from oss.language.genome_linguistics import genome_quantizer_for_language
from oss.attention.attention import MA_INBLAttention


# ── BinaryQuantizer — weight quantization ────────────────────────────────────

def test_ternary_weights_only_minus_one_zero_plus_one():
    q = BinaryQuantizer(BinaryQuantConfig(mode="ternary", threshold=0.5))
    W = np.random.default_rng(0).standard_normal((32, 64)).astype(np.float32)
    W_q, scale = q.quantize_weights(W)
    assert W_q.shape == W.shape
    assert set(np.unique(W_q)).issubset({-1.0, 0.0, 1.0})
    assert scale > 0.0


def test_binary_weights_only_minus_one_plus_one():
    q = BinaryQuantizer(BinaryQuantConfig(mode="binary"))
    W = np.random.default_rng(1).standard_normal((16, 16)).astype(np.float32)
    W_q, scale = q.quantize_weights(W)
    assert set(np.unique(W_q)).issubset({-1.0, 1.0})
    assert 0.0 not in np.unique(W_q)


def test_weight_scale_is_absmean():
    q = BinaryQuantizer()
    W = np.ones((4, 4), dtype=np.float32) * 3.0
    _, scale = q.quantize_weights(W)
    assert scale == pytest.approx(3.0)


def test_zero_weight_matrix_scale_defaults_to_one():
    q = BinaryQuantizer()
    W = np.zeros((8, 8), dtype=np.float32)
    W_q, scale = q.quantize_weights(W)
    assert scale == pytest.approx(1.0)
    assert np.all(W_q == 0.0)


# ── BinaryQuantizer — activation quantization ─────────────────────────────────

def test_activation_quantization_shape():
    q = BinaryQuantizer()
    x = np.random.default_rng(10).standard_normal((3, 5, 32)).astype(np.float32)
    x_q, scales = q.quantize_activations(x)
    assert x_q.shape == x.shape
    assert scales.shape == (3, 5, 1)


def test_activation_quantization_values_within_int8_range():
    q = BinaryQuantizer(BinaryQuantConfig(act_bits=8))
    x = np.random.default_rng(11).standard_normal((4, 64)).astype(np.float32) * 100
    x_q, _ = q.quantize_activations(x)
    assert np.all(x_q >= -127.0)
    assert np.all(x_q <= 127.0)


def test_activation_zero_input_scale_defaults_to_one():
    q = BinaryQuantizer()
    x = np.zeros((2, 8), dtype=np.float32)
    x_q, scales = q.quantize_activations(x)
    assert np.all(scales == 1.0)
    assert np.all(x_q == 0.0)


# ── BinaryQuantizer — dequantize ─────────────────────────────────────────────

def test_dequantize_scalar_scale():
    q = BinaryQuantizer()
    vals = np.array([1.0, -1.0, 0.0], dtype=np.float32)
    out = q.dequantize(vals, 2.5)
    assert np.allclose(out, [2.5, -2.5, 0.0])


def test_dequantize_array_scale():
    q = BinaryQuantizer()
    vals = np.ones((3, 4), dtype=np.float32)
    scales = np.array([[2.0], [3.0], [4.0]], dtype=np.float32)
    out = q.dequantize(vals, scales)
    assert out.shape == (3, 4)
    assert np.allclose(out[0], 2.0) and np.allclose(out[1], 3.0)


# ── BinaryQuantizer — addition-only matmul ───────────────────────────────────

def test_matmul_shape():
    q = BinaryQuantizer()
    x = np.ones((2, 8), dtype=np.float32)
    W = np.ones((8, 16), dtype=np.float32)
    W_q, W_s = q.quantize_weights(W)
    out = q.matmul(x, W_q, W_s)
    assert out.shape == (2, 16)


def test_matmul_matches_float_reference_approximately():
    rng = np.random.default_rng(42)
    W = rng.standard_normal((32, 32)).astype(np.float32)
    x = rng.standard_normal((4, 32)).astype(np.float32)
    q = BinaryQuantizer(BinaryQuantConfig(mode="binary"))
    W_q, W_s = q.quantize_weights(W)
    y_quant = q.matmul(x, W_q, W_s)
    y_ref = x @ W
    # quantized result should be correlated with float reference
    assert np.corrcoef(y_quant.ravel(), y_ref.ravel())[0, 1] > 0.5


def test_matmul_ternary_zero_columns_produce_zero():
    q = BinaryQuantizer(BinaryQuantConfig(mode="ternary", threshold=1e6))
    W = np.ones((4, 4), dtype=np.float32) * 0.1  # all below threshold → all zero
    W_q, W_s = q.quantize_weights(W)
    x = np.ones((2, 4), dtype=np.float32)
    out = q.matmul(x, W_q, W_s)
    assert np.all(out == 0.0)


# ── KernelGenome — quant_mode field ──────────────────────────────────────────

def test_kernel_genome_default_quant_mode():
    g = KernelGenome(genome_id="qm-default")
    assert g.quant_mode == "ternary"


def test_kernel_genome_mutate_sets_valid_quant_mode():
    rng_backup = __import__("random")
    g = KernelGenome(genome_id="qm-mutate")
    for _ in range(20):
        g.mutate()
        assert g.quant_mode in ("ternary", "binary")


def test_kernel_genome_crossover_inherits_quant_mode():
    a = KernelGenome(genome_id="a", quant_mode="ternary")
    b = KernelGenome(genome_id="b", quant_mode="binary")
    child = a.crossover(b)
    assert child.quant_mode in ("ternary", "binary")
    assert child.genome_id == "a+b"


# ── genome_quantizer_for_language hook ───────────────────────────────────────

def test_genome_quantizer_for_language_returns_quantizer():
    g = KernelGenome(genome_id="gql-1", quant_mode="ternary")
    q = genome_quantizer_for_language(g)
    assert isinstance(q, BinaryQuantizer)
    assert q.cfg.mode == "ternary"


def test_genome_quantizer_for_language_binary_mode():
    g = KernelGenome(genome_id="gql-2", quant_mode="binary")
    q = genome_quantizer_for_language(g)
    assert q.cfg.mode == "binary"


def test_genome_quantizer_missing_quant_mode_defaults_to_ternary():
    g = KernelGenome(genome_id="gql-3")
    del g.quant_mode  # simulate legacy genome without the field
    q = genome_quantizer_for_language(g)
    assert q.cfg.mode == "ternary"


# ── MA_INBLAttention — _project() hook ───────────────────────────────────────

def test_attention_project_without_quantizer_is_plain_matmul():
    attn = MA_INBLAttention(embed_dim=32, num_heads=4)
    x = np.ones((2, 32), dtype=np.float32)
    W = np.eye(32, dtype=np.float32) * 2.0
    out = attn._project(x, W)
    assert out.shape == (2, 32)
    assert np.allclose(out, x * 2.0)


def test_attention_project_with_quantizer_returns_same_shape():
    q = BinaryQuantizer(BinaryQuantConfig(mode="ternary"))
    attn = MA_INBLAttention(embed_dim=32, num_heads=4, quantizer=q)
    x = np.random.default_rng(99).standard_normal((3, 32)).astype(np.float32)
    W = np.random.default_rng(100).standard_normal((32, 32)).astype(np.float32)
    out = attn._project(x, W)
    assert out.shape == (3, 32)


def test_attention_project_quantized_differs_from_float():
    rng = np.random.default_rng(7)
    x = rng.standard_normal((2, 32)).astype(np.float32)
    W = rng.standard_normal((32, 32)).astype(np.float32)
    attn_q = MA_INBLAttention(
        embed_dim=32, num_heads=4,
        quantizer=BinaryQuantizer(BinaryQuantConfig(mode="binary")),
    )
    attn_f = MA_INBLAttention(embed_dim=32, num_heads=4)
    out_q = attn_q._project(x, W)
    out_f = attn_f._project(x, W)
    # quantized output is different but shapes match
    assert out_q.shape == out_f.shape
    assert not np.allclose(out_q, out_f, atol=1e-3)


def test_attention_forward_still_works_with_quantizer():
    q = BinaryQuantizer(BinaryQuantConfig(mode="ternary"))
    attn = MA_INBLAttention(embed_dim=32, num_heads=4, quantizer=q, seed=5)
    x = np.random.default_rng(5).standard_normal((1, 4, 32)).astype(np.float32)
    y, tel = attn.forward(x)
    assert y.shape == x.shape
    assert isinstance(tel, dict)
