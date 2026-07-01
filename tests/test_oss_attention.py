"""
Tests for the MA-INBL attention kernel and telemetry sink.

All tests run on the numpy reference implementation — no torch or triton required.
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np
import pytest

from oss.attention.kernel import (
    TRITON_AVAILABLE,
    MA_INBLAttentionKernelNP,
    MA_INBLAttentionKernelTriton,
    _attn_entropy,
    binary_matmul_np,
    ma_inbl_attention_np,
    ma_inbl_np,
    pack_bits_np,
    sw_popcount_np,
    sw_popcount_np_vec,
)
from oss.attention.attention import MA_INBLAttention
from oss.attention.telemetry import AttentionTelemetrySink
from oss.lab.metrics import load_logs


# ── helpers ───────────────────────────────────────────────────────────────────

def _ors(n_heads: int, head_dim: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    mats = np.zeros((n_heads, head_dim, head_dim), dtype=np.float32)
    for h in range(n_heads):
        M = rng.standard_normal((head_dim, head_dim)).astype(np.float32)
        Q, _ = np.linalg.qr(M)
        mats[h] = Q
    return mats


def _w_packed(d_model: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    w = rng.choice([-1.0, 1.0], size=(d_model, d_model)).astype(np.float32)
    return pack_bits_np(w)


# ── popcount ──────────────────────────────────────────────────────────────────

def test_popcount_zero():
    assert sw_popcount_np(0) == 0


def test_popcount_one():
    assert sw_popcount_np(1) == 1


def test_popcount_all_ones():
    assert sw_popcount_np(0xFFFFFFFF) == 32


def test_popcount_nibble():
    assert sw_popcount_np(0b1010) == 2


def test_popcount_vec_known():
    arr = np.array([0, 1, 0b1010, 0xFFFFFFFF], dtype=np.uint32)
    np.testing.assert_array_equal(sw_popcount_np_vec(arr), [0, 1, 2, 32])


def test_popcount_vec_shape_preserved():
    arr = np.ones((3, 4), dtype=np.uint32) * 0xF
    result = sw_popcount_np_vec(arr)
    assert result.shape == (3, 4)
    assert (result == 4).all()


# ── bit packing ───────────────────────────────────────────────────────────────

def test_pack_shape_32():
    packed = pack_bits_np(np.random.randn(5, 32).astype(np.float32))
    assert packed.shape == (5, 1)


def test_pack_shape_64():
    packed = pack_bits_np(np.random.randn(5, 64).astype(np.float32))
    assert packed.shape == (5, 2)


def test_pack_shape_33():
    packed = pack_bits_np(np.random.randn(2, 33).astype(np.float32))
    assert packed.shape == (2, 2)   # ceil(33/32) = 2 words


def test_pack_bit0_matches_sign():
    rng = np.random.default_rng(0)
    x = rng.standard_normal((4, 32)).astype(np.float32)
    packed = pack_bits_np(x)
    for i in range(4):
        expected = int(x[i, 0] > 0)
        actual = int((packed[i, 0] >> np.uint32(0)) & np.uint32(1))
        assert actual == expected, f"row {i}: expected bit0={expected}, got {actual}"


# ── binary matmul ─────────────────────────────────────────────────────────────

def test_bmatmul_all_agree():
    """All-positive X vs all-positive W → every bit matches → bipolar = D."""
    D = 32
    x = np.ones((1, D), dtype=np.float32)
    w = np.ones((1, D), dtype=np.float32)
    xp = pack_bits_np(x)
    wp = pack_bits_np(w)
    result = binary_matmul_np(xp, wp, D)
    assert result[0, 0] == D   # 2*32 - 32 = 32


def test_bmatmul_all_disagree():
    """All-positive X vs all-negative W → no bits match → bipolar = -D."""
    D = 32
    x = np.ones((1, D), dtype=np.float32)
    w = -np.ones((1, D), dtype=np.float32)
    xp = pack_bits_np(x)
    wp = pack_bits_np(w)
    result = binary_matmul_np(xp, wp, D)
    assert result[0, 0] == -D


def test_bmatmul_output_shape():
    rng = np.random.default_rng(7)
    x = rng.standard_normal((5, 64)).astype(np.float32)
    w = rng.standard_normal((7, 64)).astype(np.float32)
    result = binary_matmul_np(pack_bits_np(x), pack_bits_np(w), 64)
    assert result.shape == (5, 7)


def test_bmatmul_dtype():
    x = np.ones((2, 32), dtype=np.float32)
    w = np.ones((3, 32), dtype=np.float32)
    result = binary_matmul_np(pack_bits_np(x), pack_bits_np(w), 32)
    assert result.dtype == np.int32


def test_bmatmul_range():
    """Bipolar outputs must lie in [-D, D]."""
    D = 64
    rng = np.random.default_rng(3)
    x = rng.standard_normal((10, D)).astype(np.float32)
    w = rng.standard_normal((10, D)).astype(np.float32)
    result = binary_matmul_np(pack_bits_np(x), pack_bits_np(w), D)
    assert result.min() >= -D
    assert result.max() <= D


# ── MA-INBL projection ────────────────────────────────────────────────────────

def test_mainbl_output_shape():
    D, N = 64, 32
    rng = np.random.default_rng(0)
    x = rng.standard_normal((4, D)).astype(np.float32)
    w = rng.standard_normal((N, D)).astype(np.float32)
    out = ma_inbl_np(x, pack_bits_np(w), w_scale=1.0)
    assert out.shape == (4, N)


def test_mainbl_no_nan():
    rng = np.random.default_rng(1)
    x = rng.standard_normal((8, 32)).astype(np.float32)
    w = rng.standard_normal((32, 32)).astype(np.float32)
    out = ma_inbl_np(x, pack_bits_np(w), w_scale=0.1)
    assert not np.isnan(out).any()
    assert not np.isinf(out).any()


def test_mainbl_zero_input_near_zero_output():
    """Near-zero input → near-zero magnitude → near-zero output."""
    x = np.zeros((2, 32), dtype=np.float32)
    w = np.random.randn(32, 32).astype(np.float32)
    out = ma_inbl_np(x, pack_bits_np(w), w_scale=1.0)
    assert np.abs(out).max() < 1e-5


def test_mainbl_w_scale_scales_output():
    rng = np.random.default_rng(42)
    x = rng.standard_normal((3, 32)).astype(np.float32)
    w = rng.standard_normal((32, 32)).astype(np.float32)
    wp = pack_bits_np(w)
    out1 = ma_inbl_np(x, wp, w_scale=1.0)
    out2 = ma_inbl_np(x, wp, w_scale=2.0)
    np.testing.assert_allclose(out2, out1 * 2.0, rtol=1e-5)


# ── attention entropy helper ──────────────────────────────────────────────────

def test_attn_entropy_uniform():
    """Uniform distribution → entropy = log(n)."""
    n = 8
    attn = np.full((1, n), 1.0 / n)
    h = _attn_entropy(attn)
    assert abs(h - math.log(n)) < 1e-4


def test_attn_entropy_deterministic():
    """One-hot distribution → entropy ≈ 0."""
    attn = np.zeros((1, 8))
    attn[0, 3] = 1.0
    h = _attn_entropy(attn)
    assert h < 1e-3


# ── full attention pass ───────────────────────────────────────────────────────

def test_attention_output_shape():
    S, D, H = 6, 32, 4
    rng = np.random.default_rng(99)
    x = rng.standard_normal((S, D)).astype(np.float32)
    out, _ = ma_inbl_attention_np(
        x, _w_packed(D), _w_packed(D, 1), _w_packed(D, 2),
        1.0, _ors(H, D // H), n_heads=H,
    )
    assert out.shape == (S, D)


def test_attention_no_nan():
    S, D, H = 8, 32, 4
    rng = np.random.default_rng(5)
    x = rng.standard_normal((S, D)).astype(np.float32)
    out, tel = ma_inbl_attention_np(
        x, _w_packed(D), _w_packed(D, 1), _w_packed(D, 2),
        1.0, _ors(H, D // H), n_heads=H,
    )
    assert not np.isnan(out).any()
    assert not np.isinf(out).any()


def test_attention_telemetry_keys():
    S, D, H = 4, 32, 4
    rng = np.random.default_rng(7)
    x = rng.standard_normal((S, D)).astype(np.float32)
    _, tel = ma_inbl_attention_np(
        x, _w_packed(D), _w_packed(D, 1), _w_packed(D, 2),
        1.0, _ors(H, D // H), n_heads=H,
    )
    for key in ("binary_ratio", "dual_scale", "mean_attn_entropy",
                "mgc_scale_mean", "cand_mag_mean", "x_mag_mean"):
        assert key in tel, f"missing telemetry key: {key}"


def test_dual_scale_binary_ratio_1():
    """binary_ratio=1.0, training_binary_ratio=0.5 → dual_scale=0.25."""
    S, D, H = 4, 32, 4
    rng = np.random.default_rng(0)
    x = rng.standard_normal((S, D)).astype(np.float32)
    _, tel = ma_inbl_attention_np(
        x, _w_packed(D), _w_packed(D, 1), _w_packed(D, 2),
        1.0, _ors(H, D // H), n_heads=H,
        binary_ratio=1.0, training_binary_ratio=0.5,
    )
    assert abs(tel["dual_scale"] - 0.25) < 1e-6


def test_dual_scale_binary_ratio_lt1():
    """binary_ratio < 1.0 → dual_scale = 1.0 (no compensation)."""
    S, D, H = 4, 32, 4
    rng = np.random.default_rng(0)
    x = rng.standard_normal((S, D)).astype(np.float32)
    _, tel = ma_inbl_attention_np(
        x, _w_packed(D), _w_packed(D, 1), _w_packed(D, 2),
        1.0, _ors(H, D // H), n_heads=H,
        binary_ratio=0.5, training_binary_ratio=0.5,
    )
    assert abs(tel["dual_scale"] - 1.0) < 1e-6


def test_mgc_scale_in_range():
    """mgc_scale_mean must be in (0, 1] — never amplifies."""
    S, D, H = 6, 32, 4
    rng = np.random.default_rng(11)
    x = rng.standard_normal((S, D)).astype(np.float32)
    _, tel = ma_inbl_attention_np(
        x, _w_packed(D), _w_packed(D, 1), _w_packed(D, 2),
        1.0, _ors(H, D // H), n_heads=H,
    )
    assert 0.0 < tel["mgc_scale_mean"] <= 1.0 + 1e-6


def test_mgc_zero_growth_clamps_candidate():
    """max_growth=0 → |clamped| ≤ |x|, so output stays bounded."""
    S, D, H = 6, 32, 4
    rng = np.random.default_rng(13)
    x = rng.standard_normal((S, D)).astype(np.float32)
    out, _ = ma_inbl_attention_np(
        x, _w_packed(D), _w_packed(D, 1), _w_packed(D, 2),
        1.0, _ors(H, D // H), n_heads=H, max_growth=0.0,
    )
    # ORS rotation preserves norms so output magnitude ≤ 3×input
    x_mag = np.linalg.norm(x, axis=-1)
    o_mag = np.linalg.norm(out, axis=-1)
    assert np.all(o_mag < x_mag * 4.0)


def test_ors_orthogonality():
    """ORS matrices generated by MA_INBLAttention must satisfy R @ R.T ≈ I."""
    attn = MA_INBLAttention(d_model=32, n_heads=4, seed=0)
    for h in range(4):
        R = attn._ors_mat[h]
        np.testing.assert_allclose(R @ R.T, np.eye(8), atol=1e-5)


def test_temperature_affects_entropy():
    """Lower temperature → sharper attention → lower entropy."""
    S, D, H = 8, 32, 4
    rng = np.random.default_rng(55)
    x = rng.standard_normal((S, D)).astype(np.float32)
    wq, wk, wv, ors = _w_packed(D), _w_packed(D, 1), _w_packed(D, 2), _ors(H, D // H)
    _, tel_sharp = ma_inbl_attention_np(x, wq, wk, wv, 1.0, ors, n_heads=H, temperature=0.1)
    _, tel_flat   = ma_inbl_attention_np(x, wq, wk, wv, 1.0, ors, n_heads=H, temperature=10.0)
    assert tel_flat["mean_attn_entropy"] > tel_sharp["mean_attn_entropy"]


# ── MA_INBLAttention class ─────────────────────────────────────────────────────

def test_module_forward_2d():
    attn = MA_INBLAttention(d_model=32, n_heads=4, seed=0)
    x = np.random.default_rng(0).standard_normal((6, 32)).astype(np.float32)
    out, tel = attn.forward(x)
    assert out.shape == (6, 32)
    assert not np.isnan(out).any()


def test_module_forward_3d():
    attn = MA_INBLAttention(d_model=32, n_heads=4, seed=0)
    x = np.random.default_rng(0).standard_normal((3, 6, 32)).astype(np.float32)
    out, tel = attn.forward(x)
    assert out.shape == (3, 6, 32)


def test_module_raises_bad_ndim():
    attn = MA_INBLAttention(d_model=32, n_heads=4)
    with pytest.raises(ValueError):
        attn.forward(np.ones((2, 3, 4, 32), dtype=np.float32))


def test_module_raises_bad_dims():
    with pytest.raises(ValueError):
        MA_INBLAttention(d_model=33, n_heads=4)


def test_module_state_dict_keys():
    attn = MA_INBLAttention(d_model=64, n_heads=8, binary_ratio=0.8)
    sd = attn.state_dict()
    assert sd["d_model"] == 64
    assert sd["n_heads"] == 8
    assert sd["head_dim"] == 8
    assert sd["binary_ratio"] == 0.8
    assert "triton_available" in sd


def test_triton_available_flag():
    assert isinstance(TRITON_AVAILABLE, bool)


# ── telemetry ─────────────────────────────────────────────────────────────────

def _fake_tel(**kw) -> dict:
    base = {
        "binary_ratio": 1.0, "dual_scale": 1.0,
        "mean_attn_entropy": 2.0, "mgc_scale_mean": 0.9,
        "cand_mag_mean": 1.5, "x_mag_mean": 1.2,
    }
    base.update(kw)
    return base


def test_telemetry_record_and_load():
    with tempfile.TemporaryDirectory() as tmp:
        sink = AttentionTelemetrySink(log_path=Path(tmp) / "t.jsonl")
        r = sink.record(_fake_tel())
        assert r["step"] == 0
        entries = sink.load_session()
        assert len(entries) == 1
        assert entries[0]["binary_ratio"] == 1.0


def test_telemetry_step_increments():
    with tempfile.TemporaryDirectory() as tmp:
        sink = AttentionTelemetrySink(log_path=Path(tmp) / "t.jsonl")
        for _ in range(5):
            sink.record(_fake_tel())
        entries = sink.load_session()
        assert [e["step"] for e in entries] == list(range(5))


def test_telemetry_load_all_includes_all_sessions():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "t.jsonl"
        sink1 = AttentionTelemetrySink(log_path=p)
        sink1.record(_fake_tel())
        sink2 = AttentionTelemetrySink(log_path=p)
        sink2.record(_fake_tel())
        assert len(sink2.load_all()) == 2


def test_telemetry_summary_mean_dual_scale():
    with tempfile.TemporaryDirectory() as tmp:
        sink = AttentionTelemetrySink(log_path=Path(tmp) / "t.jsonl")
        sink.record(_fake_tel(dual_scale=0.25))
        s = sink.summary()
        assert s["steps"] == 1
        assert abs(s["mean_dual_scale"] - 0.25) < 1e-6


def test_telemetry_extra_fields():
    with tempfile.TemporaryDirectory() as tmp:
        sink = AttentionTelemetrySink(log_path=Path(tmp) / "t.jsonl")
        sink.record(_fake_tel(), extra={"model_ver": "v2"})
        assert sink.load_all()[0]["model_ver"] == "v2"


def test_telemetry_empty_summary():
    with tempfile.TemporaryDirectory() as tmp:
        sink = AttentionTelemetrySink(log_path=Path(tmp) / "t.jsonl")
        s = sink.summary()
        assert s["steps"] == 0


# ── end-to-end: attention forward → telemetry sink ───────────────────────────

def test_e2e_attention_with_telemetry():
    with tempfile.TemporaryDirectory() as tmp:
        attn = MA_INBLAttention(
            d_model=32, n_heads=4, seed=42,
            binary_ratio=1.0, training_binary_ratio=0.8,
        )
        sink = AttentionTelemetrySink(log_path=Path(tmp) / "e2e.jsonl")
        rng = np.random.default_rng(42)
        for _ in range(3):
            x = rng.standard_normal((5, 32)).astype(np.float32)
            _, tel = attn.forward(x)
            sink.record(tel, agent_id="gh05t3_attn")
        s = sink.summary()
        assert s["steps"] == 3
        assert s["mean_mean_attn_entropy"] > 0.0
        assert 0.0 < s["mean_mgc_scale_mean"] <= 1.0 + 1e-6


# ── spec tests (new API: embed_dim / num_heads / ors_matrix) ──────────────────

def test_spec_forward_shape():
    """Spec test 1: forward output shape matches input."""
    x = np.random.randn(1, 64, 128).astype(np.float32)
    attn = MA_INBLAttention(embed_dim=128, num_heads=4)
    y, _ = attn.forward(x)
    assert y.shape == x.shape


def test_spec_magnitude_nonzero():
    """Spec test 2: output magnitude is non-zero for random input."""
    x = np.random.randn(1, 64, 128).astype(np.float32)
    attn = MA_INBLAttention(embed_dim=128, num_heads=4)
    y, _ = attn.forward(x)
    assert np.linalg.norm(y) > 0


def test_spec_dual_scale_consistency():
    """
    Spec test 3: changing training_binary_ratio should not alter output norm
    because binary_ratio defaults to 0.0 → dual_scale = 1.0 in both cases,
    so the computation is identical and norms are equal.
    """
    x = np.random.randn(1, 64, 128).astype(np.float32)
    attn = MA_INBLAttention(embed_dim=128, num_heads=4, seed=99)

    attn.training_binary_ratio = 0.95
    y1, _ = attn.forward(x)

    attn.training_binary_ratio = 1.0
    y2, _ = attn.forward(x)

    # binary_ratio=0.0 (class default) → dual_scale=1.0 for both → y1 == y2
    assert abs(np.linalg.norm(y1) - np.linalg.norm(y2)) < 1e-3


def test_spec_telemetry_log_and_load():
    """Spec test 4: log() writes to the oss.lab metrics store and load_logs finds it."""
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "spec_attn.jsonl"
        sink = AttentionTelemetrySink(log_path=log_path)
        sink.log(
            {"mean_mag_x": 1.0, "mean_candidate_mag": 1.2, "mean_mgc_scale": 0.9},
            log_path=log_path,
        )
        entries = load_logs(path=log_path)
        assert len(entries) > 0


def test_spec_ors_identity_shape():
    """Spec test 5: ORS=eye(128) → output shape is preserved."""
    ORS = np.eye(128, dtype=np.float32)
    x = np.random.randn(1, 64, 128).astype(np.float32)
    attn = MA_INBLAttention(embed_dim=128, num_heads=4, ors_matrix=ORS)
    y, _ = attn.forward(x)
    assert y.shape == x.shape


def test_kernel_np_callable():
    """MA_INBLAttentionKernelNP is callable and returns expected shapes."""
    kern = MA_INBLAttentionKernelNP()
    assert kern.available
    D, S, H = 32, 4, 4
    rng = np.random.default_rng(0)
    x = rng.standard_normal((S, D)).astype(np.float32)
    wq, wk, wv = _w_packed(D), _w_packed(D, 1), _w_packed(D, 2)
    ors = _ors(H, D // H)
    out, tel = kern(x, wq, wk, wv, 1.0, ors, n_heads=H)
    assert out.shape == (S, D)


def test_kernel_triton_stub_raises():
    """MA_INBLAttentionKernelTriton raises RuntimeError when Triton missing."""
    kern = MA_INBLAttentionKernelTriton()
    if not TRITON_AVAILABLE:
        with pytest.raises(RuntimeError):
            kern()
    else:
        # When triton IS available the stub raises NotImplementedError
        with pytest.raises(NotImplementedError):
            kern()
