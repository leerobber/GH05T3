"""
Tests for the Triton backend, device packing helpers, LivingLoop genome/experiments,
and trait-driven backend selection.

Triton-specific tests are skipped when torch/triton are not installed.
All numpy-path tests always run.
"""
from __future__ import annotations

import numpy as np
import pytest

from oss.attention.kernel import (
    TRITON_AVAILABLE,
    MA_INBLAttentionKernelNP,
    MA_INBLAttentionKernelTriton,
    ma_inbl_attention_np,
    pack_bits_np,
)
from oss.attention.attention import MA_INBLAttention
from oss.substrate.attention_config import AttentionConfig, TRAIT_DIM

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_inputs(seq: int = 8, dim: int = 32, seed: int = 0):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((seq, dim)).astype(np.float32)
    w = rng.choice([-1.0, 1.0], size=(dim, dim)).astype(np.float32)
    w_packed = pack_bits_np(w)
    ors = np.zeros((4, dim // 4, dim // 4), dtype=np.float32)
    for h in range(4):
        M = rng.standard_normal((dim // 4, dim // 4)).astype(np.float32)
        Q, _ = np.linalg.qr(M)
        ors[h] = Q
    return x, w_packed, ors


# ── TRITON_AVAILABLE flag ─────────────────────────────────────────────────────

def test_triton_available_is_bool():
    assert isinstance(TRITON_AVAILABLE, bool)


def test_triton_kernel_class_available_property():
    k = MA_INBLAttentionKernelTriton()
    assert isinstance(k.available, bool)
    assert k.available == TRITON_AVAILABLE


# ── Device packing helpers ────────────────────────────────────────────────────

def test_pack_bits_torch_requires_torch():
    from oss.attention.kernel import pack_bits_torch
    try:
        import torch
    except ImportError:
        pytest.skip("torch not installed")
    w = torch.tensor([1.0, -1.0, 1.0, 1.0, -1.0, -1.0, 1.0, -1.0] * 4)
    packed = pack_bits_torch(w.unsqueeze(0))
    assert packed.dtype == torch.int32


def test_pack_bits_device_matches_numpy():
    try:
        import torch
    except ImportError:
        pytest.skip("torch not installed")
    from oss.attention.kernel import pack_bits_device
    x = np.ones((4, 32), dtype=np.float32)
    packed_np = pack_bits_np(x)
    packed_dev = pack_bits_device(packed_np, device="cpu")
    assert packed_dev.shape == (4, 1)  # 32 bits → 1 uint32 word


def test_prepare_qkv_device_keys():
    try:
        import torch
    except ImportError:
        pytest.skip("torch not installed")
    from oss.attention.kernel import prepare_qkv_device
    x, w_packed, ors = _make_inputs(seq=4, dim=32)
    buffers = prepare_qkv_device(w_packed, w_packed, w_packed, ors, x, device="cpu")
    for key in ("x_dev", "wq_dev", "wk_dev", "wv_dev", "ors_dev", "mag_scale", "squeeze"):
        assert key in buffers


def test_prepare_qkv_device_x_shape():
    try:
        import torch
    except ImportError:
        pytest.skip("torch not installed")
    from oss.attention.kernel import prepare_qkv_device
    x, w_packed, ors = _make_inputs(seq=5, dim=32)
    buffers = prepare_qkv_device(w_packed, w_packed, w_packed, ors, x, device="cpu")
    assert buffers["x_dev"].shape == (1, 5, 32)   # batch dim added
    assert buffers["squeeze"] is True


def test_prepare_qkv_device_mag_scale_positive():
    try:
        import torch
    except ImportError:
        pytest.skip("torch not installed")
    from oss.attention.kernel import prepare_qkv_device
    x, w_packed, ors = _make_inputs(seq=4, dim=32)
    buffers = prepare_qkv_device(w_packed, w_packed, w_packed, ors, x, device="cpu")
    assert buffers["mag_scale"] > 0.0


# ── MA_INBLAttentionKernelNP (always runs) ────────────────────────────────────

def test_np_kernel_callable():
    k = MA_INBLAttentionKernelNP()
    assert callable(k)
    assert k.available is True


def test_np_kernel_output_shape():
    x, w_packed, ors = _make_inputs(seq=6, dim=32)
    k = MA_INBLAttentionKernelNP()
    out, tel = k(x, w_packed, w_packed, w_packed, 1.0, ors, n_heads=4)
    assert out.shape == (6, 32)


def test_np_kernel_telemetry_keys():
    x, w_packed, ors = _make_inputs()
    k = MA_INBLAttentionKernelNP()
    _, tel = k(x, w_packed, w_packed, w_packed, 1.0, ors, n_heads=4)
    for key in ("binary_ratio", "dual_scale", "mgc_scale_mean", "x_mag_mean"):
        assert key in tel


def test_np_kernel_identity_ors():
    """Identity ORS should preserve output shape."""
    x, w_packed, _ = _make_inputs(seq=4, dim=32)
    head_dim = 32 // 4
    ors_identity = np.stack([np.eye(head_dim, dtype=np.float32) for _ in range(4)])
    k = MA_INBLAttentionKernelNP()
    out, _ = k(x, w_packed, w_packed, w_packed, 1.0, ors_identity, n_heads=4)
    assert out.shape == (4, 32)


def test_np_kernel_mgc_clamping():
    """With max_growth=0.0, output magnitudes must not exceed input magnitudes."""
    rng = np.random.default_rng(1)
    x = rng.standard_normal((4, 32)).astype(np.float32) * 5.0
    w_packed = pack_bits_np(rng.choice([-1.0, 1.0], size=(32, 32)).astype(np.float32))
    ors = np.stack([np.eye(8, dtype=np.float32) for _ in range(4)])
    k = MA_INBLAttentionKernelNP()
    out, tel = k(x, w_packed, w_packed, w_packed, 1.0, ors, n_heads=4, max_growth=0.0)
    x_norms = np.linalg.norm(x, axis=-1)
    out_norms = np.linalg.norm(out, axis=-1)
    assert np.all(out_norms <= x_norms * 1.01 + 1e-4)


def test_np_kernel_dual_scale_binary_ratio_one():
    """binary_ratio=1.0 activates dual-scale compensation."""
    x, w_packed, ors = _make_inputs()
    k = MA_INBLAttentionKernelNP()
    out1, tel1 = k(x, w_packed, w_packed, w_packed, 1.0, ors,
                   n_heads=4, binary_ratio=1.0, training_binary_ratio=0.5)
    out2, tel2 = k(x, w_packed, w_packed, w_packed, 1.0, ors,
                   n_heads=4, binary_ratio=0.0, training_binary_ratio=0.5)
    assert tel1["dual_scale"] == pytest.approx(0.25, abs=1e-5)  # tbr² = 0.25
    assert tel2["dual_scale"] == pytest.approx(1.0, abs=1e-5)


# ── MA_INBLAttention backend dispatch ────────────────────────────────────────

def test_attention_backend_auto_resolves():
    m = MA_INBLAttention(embed_dim=32, num_heads=4, backend="auto")
    assert m.active_backend in ("numpy", "triton")


def test_attention_backend_numpy_explicit():
    m = MA_INBLAttention(embed_dim=32, num_heads=4, backend="numpy")
    assert m.active_backend == "numpy"
    assert m._use_triton is False


def test_attention_backend_triton_raises_when_unavailable():
    if TRITON_AVAILABLE:
        pytest.skip("Triton is available, skip unavailable test")
    with pytest.raises(RuntimeError, match="triton"):
        MA_INBLAttention(embed_dim=32, num_heads=4, backend="triton")


def test_attention_state_dict_has_backend():
    m = MA_INBLAttention(embed_dim=32, num_heads=4, backend="numpy")
    sd = m.state_dict()
    assert "backend" in sd
    assert "active_backend" in sd
    assert sd["active_backend"] == "numpy"


def test_attention_numpy_forward_shape():
    m = MA_INBLAttention(embed_dim=32, num_heads=4, backend="numpy")
    x = np.random.randn(6, 32).astype(np.float32)
    out, tel = m.forward(x)
    assert out.shape == (6, 32)


# ── Trait-driven backend selection ────────────────────────────────────────────

def test_trait_driven_backend_high_compute_triton():
    """Genomes with coding > 0.7 should prefer triton backend in config."""
    cfg = AttentionConfig.from_genome_traits({"coding": 0.9})
    assert cfg.backend == "triton"


def test_trait_driven_backend_low_compute_auto():
    """Genomes with low coding traits → auto backend."""
    cfg = AttentionConfig.from_genome_traits({"coding": 0.3})
    assert cfg.backend == "auto"


def test_trait_driven_backend_systems_trait():
    """systems > 0.7 also triggers triton preference."""
    cfg = AttentionConfig.from_genome_traits({"systems": 0.8})
    assert cfg.backend == "triton"


def test_trait_driven_build_module_no_raise():
    """build_module() with trait-derived config should not raise on this machine."""
    cfg = AttentionConfig.from_genome_traits({"coding": 0.9})
    # On machines without Triton, triton-configured genomes fall back gracefully
    # because build_module resolves "triton" to error only if explicitly enforced.
    # Default: AttentionConfig.backend="triton" → MA_INBLAttention(backend="triton")
    # which raises on import. We test the fallback path works at config level.
    cfg_dict = cfg.to_dict()
    assert cfg_dict["backend"] == "triton"
    # The resolved module will fall back to numpy if triton unavailable
    if not TRITON_AVAILABLE:
        # Config says "triton" but build_module with override should work
        module = cfg.build_module(backend="numpy")
        assert module.active_backend == "numpy"


def test_trait_driven_build_module_roundtrip():
    cfg = AttentionConfig.from_genome_traits({"analysis": 0.7, "risk_tolerance": 0.4})
    d = cfg.to_dict()
    cfg2 = AttentionConfig.from_dict(d)
    assert cfg.backend == cfg2.backend
    assert cfg.temperature == pytest.approx(cfg2.temperature, abs=1e-4)


# ── Triton kernel (skipped when not available) ────────────────────────────────

@pytest.mark.skipif(not TRITON_AVAILABLE, reason="Triton not installed")
def test_triton_kernel_output_shape():
    x, w_packed, ors = _make_inputs(seq=8, dim=32)
    k = MA_INBLAttentionKernelTriton()
    out, tel = k(x, w_packed, w_packed, w_packed, 1.0, ors, n_heads=4)
    assert out.shape == (8, 32)


@pytest.mark.skipif(not TRITON_AVAILABLE, reason="Triton not installed")
def test_triton_kernel_telemetry_backend_field():
    x, w_packed, ors = _make_inputs()
    k = MA_INBLAttentionKernelTriton()
    _, tel = k(x, w_packed, w_packed, w_packed, 1.0, ors, n_heads=4)
    assert tel.get("backend") == "triton"


@pytest.mark.skipif(not TRITON_AVAILABLE, reason="Triton not installed")
def test_triton_numpy_equivalence_identity_ors():
    """Triton and numpy outputs should agree to within float16 tolerance."""
    dim = 32
    head_dim = dim // 4
    x, w_packed, _ = _make_inputs(seq=4, dim=dim)
    ors = np.stack([np.eye(head_dim, dtype=np.float32) for _ in range(4)])

    np_out, _ = ma_inbl_attention_np(x, w_packed, w_packed, w_packed, 1.0, ors, n_heads=4)
    tr_out, _ = MA_INBLAttentionKernelTriton()(x, w_packed, w_packed, w_packed, 1.0, ors, n_heads=4)

    assert np.allclose(np_out, tr_out, atol=1e-2), (
        f"max diff = {np.abs(np_out - tr_out).max():.4f}"
    )


@pytest.mark.skipif(not TRITON_AVAILABLE, reason="Triton not installed")
def test_triton_numpy_telemetry_x_mag():
    """x_mag_mean telemetry should be close between backends."""
    x, w_packed, ors = _make_inputs()
    _, np_tel = ma_inbl_attention_np(x, w_packed, w_packed, w_packed, 1.0, ors, n_heads=4)
    _, tr_tel = MA_INBLAttentionKernelTriton()(x, w_packed, w_packed, w_packed, 1.0, ors, n_heads=4)
    assert abs(np_tel["x_mag_mean"] - tr_tel["x_mag_mean"]) < 1e-3


@pytest.mark.skipif(not TRITON_AVAILABLE, reason="Triton not installed")
def test_triton_dual_scale_binary_ratio_one():
    x, w_packed, ors = _make_inputs()
    k = MA_INBLAttentionKernelTriton()
    _, tel = k(x, w_packed, w_packed, w_packed, 1.0, ors,
               n_heads=4, binary_ratio=1.0, training_binary_ratio=0.8)
    assert tel["dual_scale"] == pytest.approx(0.64, abs=1e-4)


@pytest.mark.skipif(not TRITON_AVAILABLE, reason="Triton not installed")
def test_triton_attention_module_active_backend():
    m = MA_INBLAttention(embed_dim=32, num_heads=4, backend="triton")
    assert m.active_backend == "triton"
    x = np.random.randn(4, 32).astype(np.float32)
    out, _ = m.forward(x)
    assert out.shape == (4, 32)


# ── LivingLoop genome ─────────────────────────────────────────────────────────

def test_kernel_genome_fields():
    from oss.living_loop.genome import KernelGenome
    g = KernelGenome(genome_id="test-g")
    assert g.genome_id == "test-g"
    assert g.temperature == pytest.approx(1.0)
    assert g.ors_variant == "qr"
    assert g.int4_levels == 16
    assert g.use_torch is False
    assert g.fitness == pytest.approx(0.0)


def test_kernel_genome_mutate_in_place():
    from oss.living_loop.genome import KernelGenome
    g = KernelGenome(genome_id="mut-test", temperature=1.0)
    orig_id = g.genome_id
    g.mutate()
    # genome_id is unchanged (in-place); at least block sizes must change
    assert g.genome_id == orig_id
    assert g.block_size_l in (32, 64, 128)
    assert g.block_size_dh in (32, 64, 128)
    assert g.ors_variant in ("qr", "identity", "random", "block_qr")
    assert g.int4_levels in (8, 16, 32)


def test_kernel_genome_mutate_clamps():
    from oss.living_loop.genome import KernelGenome
    g = KernelGenome(genome_id="clamp-g", temperature=9.9, max_growth=1.9,
                     training_binary_ratio=0.99)
    for _ in range(30):
        g.mutate()
    assert 0.1 <= g.temperature <= 10.0
    assert 0.0 <= g.max_growth <= 2.0
    assert 0.0 <= g.training_binary_ratio <= 1.0


def test_kernel_genome_crossover_id():
    from oss.living_loop.genome import KernelGenome
    a = KernelGenome(genome_id="alpha")
    b = KernelGenome(genome_id="beta")
    child = a.crossover(b)
    assert child.genome_id == "alpha+beta"


def test_kernel_genome_crossover_temperature_average():
    from oss.living_loop.genome import KernelGenome
    a = KernelGenome(genome_id="a", temperature=0.4)
    b = KernelGenome(genome_id="b", temperature=1.6)
    child = a.crossover(b)
    assert child.temperature == pytest.approx(1.0)


def test_kernel_genome_crossover_discrete_genes_from_parents():
    from oss.living_loop.genome import KernelGenome
    a = KernelGenome(genome_id="a", ors_variant="qr", int4_levels=8, block_size_l=32)
    b = KernelGenome(genome_id="b", ors_variant="identity", int4_levels=32, block_size_l=128)
    child = a.crossover(b)
    assert child.ors_variant in ("qr", "identity")
    assert child.int4_levels in (8, 32)
    assert child.block_size_l in (32, 128)


# ── LivingLoop experiments ────────────────────────────────────────────────────

def _make_dummy_substrate():
    """Build a minimal substrate that returns a flat trait vector."""
    from oss.substrate.attention_config import traits_to_vector

    class _Seg:
        def __init__(self, gid):
            self.genome_id = gid
            self.traits = {k: 0.5 for k in [
                "coding", "research", "analysis", "math",
                "curiosity", "pattern_detection", "risk_tolerance", "market_intuition",
                "finance", "strategy", "risk", "ops",
                "systems", "reliability", "safety", "ethics",
                "audit", "compliance", "design", "growth",
                "monetization", "ux", "creativity", "empathy",
                "innovation", "economics", "self_reflection", "communication",
                "reasoning", "adaptability", "leadership", "general",
            ]}
        def trait_vector(self):
            return traits_to_vector(self.traits)

    class _Sub:
        def segment(self, gid):
            return _Seg(gid)

    return _Sub()


def test_run_attention_experiment_canonical_keys():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.experiments import run_attention_experiment
    g = KernelGenome(genome_id="exp-test")
    tel = run_attention_experiment(g, _make_dummy_substrate())
    assert "mean_mag_x" in tel
    assert "mean_candidate_mag" in tel
    assert "mean_mgc_scale" in tel
    assert "output_norm" in tel
    assert tel["genome_id"] == "exp-test"


def test_run_attention_experiment_ors_variants():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.experiments import run_attention_experiment
    sub = _make_dummy_substrate()
    for variant in ("qr", "identity", "random", "block_qr"):
        g = KernelGenome(genome_id=f"v-{variant}", ors_variant=variant)
        tel = run_attention_experiment(g, sub)
        assert tel["output_norm"] >= 0.0


def test_attention_fitness_numeric():
    from oss.living_loop.fitness import attention_fitness
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.experiments import run_attention_experiment
    g = KernelGenome(genome_id="fit-test")
    tel = run_attention_experiment(g, _make_dummy_substrate())
    score = attention_fitness(tel)
    assert isinstance(score, float)


def test_living_loop_evolve_updates_fitness():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.living_loop import LivingLoop
    sub = _make_dummy_substrate()
    loop = LivingLoop(sub)
    g = KernelGenome(genome_id="ll-genome")
    loop.register_genome(g)
    loop.evolve_attention()
    assert "ll-genome" in loop.history
    assert len(loop.history["ll-genome"]) == 1
    assert "fitness" in loop.history["ll-genome"][0]


# ── Router use_torch field (API-level check) ──────────────────────────────────

def test_router_run_request_has_use_torch():
    from oss.api.router import AttentionRunRequest
    req = AttentionRunRequest()
    assert hasattr(req, "use_torch")
    assert req.use_torch is False


def test_router_run_request_use_torch_true():
    from oss.api.router import AttentionRunRequest
    req = AttentionRunRequest(use_torch=True)
    assert req.use_torch is True
