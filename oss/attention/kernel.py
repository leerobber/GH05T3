"""
MA-INBL fused attention kernel — fixed Triton implementation + numpy reference.

Components:
  MA-INBL   — MagnitudeAwareINBL: unit-direction binary linear + INT4 magnitude
  BinLinear — XNOR+popcount on bit-packed weights / activations
  Dual-scale — compensation multiplier applied when binary_ratio == 1.0
  MGC        — Magnitude Growth Clamping on the residual candidate
  ORS        — Orthogonal Residual Stream rotation per head

The Triton kernel requires ``torch`` and ``triton``; the numpy reference is
always available and is used by the test suite.
"""
from __future__ import annotations

import math
import numpy as np


# ── Device tensor packing helpers (require torch; always importable as stubs) ─

def pack_bits_torch(w: "Any") -> "Any":  # type: ignore[name-defined]
    """
    Pack a ±1 float32 weight tensor into uint32 bit words (torch version).

    w   : [..., D]  float32 tensor on any device (positive → bit=1)
    Returns [..., ceil(D/32)]  int32 tensor (torch has no uint32)
    """
    import torch
    D = w.shape[-1]
    n_words = (D + 31) // 32
    padded_D = n_words * 32
    # Pad to multiple of 32
    pad = torch.zeros(*w.shape[:-1], padded_D, dtype=torch.bool, device=w.device)
    pad[..., :D] = w > 0
    packed = torch.zeros(*w.shape[:-1], n_words, dtype=torch.int32, device=w.device)
    for b in range(32):
        packed = packed | (pad[..., b::32].to(torch.int32) << b)
    return packed


def pack_bits_device(
    w_packed_np: "np.ndarray",  # [N, n_words] uint32 from pack_bits_np
    device: str = "cuda",
) -> "Any":  # type: ignore[name-defined]
    """
    Move a pre-packed uint32 numpy array to a torch device tensor (int32).

    Accepts the output of pack_bits_np() directly.
    """
    import torch
    return torch.from_numpy(w_packed_np.view(np.int32)).to(device)


def prepare_qkv_device(
    wq_packed: "np.ndarray",
    wk_packed: "np.ndarray",
    wv_packed: "np.ndarray",
    ors_mat: "np.ndarray",
    x: "np.ndarray",
    *,
    device: str = "cuda",
) -> "dict[str, Any]":  # type: ignore[name-defined]
    """
    Convert all MA-INBL inputs to device tensors ready for Triton launch.

    Returns a dict:
        x_dev    : [B, S, D] float32 device tensor  (batch dim added if 2-D)
        wq_dev   : [N_words, D]  int32 device tensor (packed binary weights)
        wk_dev   : same
        wv_dev   : same
        ors_dev  : [H, Dh, Dh] float32 device tensor
        mag_scale: float (global magnitude scale for INT4 dequant)
    """
    import torch
    x_np = x.astype(np.float32)
    squeeze = x_np.ndim == 2
    if squeeze:
        x_np = x_np[None, ...]   # [1, S, D]

    mag = float(np.linalg.norm(x_np, axis=-1).max()) + 1e-8

    return {
        "x_dev"    : torch.from_numpy(x_np).to(device),
        "wq_dev"   : pack_bits_device(wq_packed, device),
        "wk_dev"   : pack_bits_device(wk_packed, device),
        "wv_dev"   : pack_bits_device(wv_packed, device),
        "ors_dev"  : torch.from_numpy(ors_mat.astype(np.float32)).to(device),
        "mag_scale": mag,
        "squeeze"  : squeeze,
    }

# ── numpy reference implementations ───────────────────────────────────────────

def sw_popcount_np(x: int) -> int:
    """Hamming weight (popcount) for a single 32-bit integer."""
    x = x & 0xFFFFFFFF
    x = x - ((x >> 1) & 0x55555555)
    x = (x & 0x33333333) + ((x >> 2) & 0x33333333)
    x = (x + (x >> 4)) & 0x0F0F0F0F
    return ((x * 0x01010101) >> 24) & 0xFF


def sw_popcount_np_vec(arr: np.ndarray) -> np.ndarray:
    """Vectorized popcount for a uint32 array (any shape → same shape, int32)."""
    x = arr.astype(np.uint32)
    x = x - ((x >> np.uint32(1)) & np.uint32(0x55555555))
    x = (x & np.uint32(0x33333333)) + ((x >> np.uint32(2)) & np.uint32(0x33333333))
    x = (x + (x >> np.uint32(4))) & np.uint32(0x0F0F0F0F)
    return ((x * np.uint32(0x01010101)) >> np.uint32(24)).astype(np.int32)


def pack_bits_np(x: np.ndarray) -> np.ndarray:
    """
    Pack binarized activations into uint32 words.

    Input: [..., D]  float — positive values become bit=1, non-positive → bit=0
    Output: [..., ceil(D/32)]  uint32
    """
    D = x.shape[-1]
    n_words = (D + 31) // 32
    padded_D = n_words * 32
    padded = np.zeros(x.shape[:-1] + (padded_D,), dtype=np.uint32)
    padded[..., :D] = (x > 0).astype(np.uint32)
    packed = np.zeros(x.shape[:-1] + (n_words,), dtype=np.uint32)
    for b in range(32):
        packed = packed | (padded[..., b::32] << np.uint32(b))
    return packed


def binary_matmul_np(
    x_packed: np.ndarray,
    w_packed: np.ndarray,
    n_bits: int,
) -> np.ndarray:
    """
    XNOR+popcount matmul (numpy reference).

    x_packed : [M, n_words]  uint32
    w_packed  : [N, n_words]  uint32
    n_bits    : full bit-width D used for bipolar normalisation
    Returns   : [M, N]  int32  bipolar = 2*popcount(xnor) - n_bits
    """
    # Broadcast: [M, 1, n_words] ^ [1, N, n_words] → [M, N, n_words]
    xnor = (
        ~(x_packed[:, None, :] ^ w_packed[None, :, :]) & np.uint32(0xFFFFFFFF)
    )
    M, N, n_words = xnor.shape
    pop = sw_popcount_np_vec(xnor.ravel()).reshape(M, N, n_words).sum(axis=-1)
    return (2 * pop - n_bits).astype(np.int32)


def ma_inbl_np(
    x: np.ndarray,
    w_packed: np.ndarray,
    w_scale: float,
    *,
    n_int4: int = 16,
) -> np.ndarray:
    """
    MA-INBL forward pass (numpy reference).

    Decomposes x into unit direction + scalar magnitude, applies a BinaryLinear
    layer to the direction vector, and dequantises the magnitude via INT4.

    x        : [M, D]           float32
    w_packed : [N, D//32]       uint32  bit-packed binary weights
    w_scale  : float            weight scale factor
    Returns  : [M, N]           float32
    """
    M, D = x.shape
    n_words = w_packed.shape[1]

    # Direction decomposition
    mag = np.linalg.norm(x, axis=-1, keepdims=True)   # [M, 1]
    mag = np.maximum(mag, 1e-8)
    direction = x / mag                                # unit vector [M, D]

    # INT4 magnitude quantisation (STE dequant: mag_q * mag_scale)
    mag_max = float(mag.max()) + 1e-8
    mag_scale = mag_max / n_int4
    mag_q = np.clip(np.round(mag / mag_scale).astype(np.int32), 0, n_int4 - 1)
    mag_dequant = mag_q.astype(np.float32) * mag_scale    # [M, 1]

    # Pack direction bits and run XNOR matmul
    dir_packed = pack_bits_np(direction)               # [M, n_words]
    bipolar = binary_matmul_np(dir_packed, w_packed, D)  # [M, N]

    # Scale: bipolar ∈ [-D, D] → normalise to [-1, 1], apply magnitude + weight scale
    out = bipolar.astype(np.float32) * (w_scale * mag_dequant / D)
    return out


def _attn_entropy(attn: np.ndarray) -> float:
    """Mean Shannon entropy of an attention weight matrix (last 2-D slice)."""
    p = np.clip(attn, 1e-12, 1.0)
    return float(-(p * np.log(p)).sum(axis=-1).mean())


def ma_inbl_attention_np(
    x: np.ndarray,
    wq_packed: np.ndarray,
    wk_packed: np.ndarray,
    wv_packed: np.ndarray,
    w_scale: float,
    ors_mat: np.ndarray,
    *,
    n_heads: int = 8,
    temperature: float = 1.0,
    binary_ratio: float = 1.0,
    training_binary_ratio: float = 1.0,
    max_growth: float = 0.5,
    n_int4: int = 16,
) -> tuple[np.ndarray, dict]:
    """
    Full MA-INBL attention with MGC + ORS (numpy reference).

    x          : [seq_len, d_model]              float32
    wq/wk/wv   : [d_model, d_model//32]          uint32  bit-packed
    w_scale    : float
    ors_mat    : [n_heads, head_dim, head_dim]    float32  orthogonal per head
    Returns    : (output [seq_len, d_model], telemetry dict)
    """
    seq_len, d_model = x.shape
    head_dim = d_model // n_heads
    if d_model % n_heads != 0:
        raise ValueError(f"d_model={d_model} must be divisible by n_heads={n_heads}")

    # ── MA-INBL projections ───────────────────────────────────────────────────
    Q = ma_inbl_np(x, wq_packed, w_scale, n_int4=n_int4)   # [S, d_model]
    K = ma_inbl_np(x, wk_packed, w_scale, n_int4=n_int4)
    V = ma_inbl_np(x, wv_packed, w_scale, n_int4=n_int4)

    # ── Dual-scale compensation ───────────────────────────────────────────────
    # Applied only when fully binarised (binary_ratio == 1.0)
    dual_scale = (training_binary_ratio ** 2) if binary_ratio == 1.0 else 1.0

    # ── Per-head scaled dot-product attention ─────────────────────────────────
    Q = Q.reshape(seq_len, n_heads, head_dim)
    K = K.reshape(seq_len, n_heads, head_dim)
    V = V.reshape(seq_len, n_heads, head_dim)
    O = np.zeros_like(Q)
    last_attn: np.ndarray | None = None

    inv_sqrt = 1.0 / math.sqrt(head_dim)
    for h in range(n_heads):
        Qh = Q[:, h, :]   # [S, Dh]
        Kh = K[:, h, :]
        Vh = V[:, h, :]
        # Numerically stable softmax
        scores = Qh @ Kh.T * inv_sqrt * dual_scale   # [S, S]
        scores = (scores - scores.max(axis=-1, keepdims=True)) / temperature
        ew = np.exp(scores)
        attn_w = ew / (ew.sum(axis=-1, keepdims=True) + 1e-8)
        O[:, h, :] = attn_w @ Vh
        last_attn = attn_w

    O_flat = O.reshape(seq_len, d_model)

    # ── MGC: Magnitude Growth Clamping ───────────────────────────────────────
    x_mag = np.linalg.norm(x, axis=-1, keepdims=True)        # [S, 1]
    max_allowed = x_mag * (1.0 + max_growth)
    candidate = x + O_flat
    cand_mag = np.linalg.norm(candidate, axis=-1, keepdims=True)
    mgc_scale = np.where(
        cand_mag > max_allowed,
        max_allowed / (cand_mag + 1e-8),
        1.0,
    )                                                          # [S, 1] ∈ (0, 1]
    clamped = candidate * mgc_scale                           # [S, d_model]

    # ── ORS: Orthogonal Residual Stream ───────────────────────────────────────
    O_delta = (clamped - x).reshape(seq_len, n_heads, head_dim)
    rotated_h = np.zeros_like(O_delta)
    for h in range(n_heads):
        rotated_h[:, h, :] = O_delta[:, h, :] @ ors_mat[h]   # [S, Dh] @ [Dh, Dh]
    output = x + rotated_h.reshape(seq_len, d_model)

    # Final output scale for dual-scale path
    if binary_ratio == 1.0:
        output = output * training_binary_ratio

    telemetry = {
        "binary_ratio": float(binary_ratio),
        "dual_scale": float(dual_scale),
        "mean_attn_entropy": _attn_entropy(last_attn) if last_attn is not None else 0.0,
        "mgc_scale_mean": float(mgc_scale.mean()),
        "cand_mag_mean": float(cand_mag.mean()),
        "x_mag_mean": float(x_mag.mean()),
    }
    return output, telemetry


# ── Class wrappers (callable objects for both backends) ───────────────────────

class MA_INBLAttentionKernelNP:
    """
    Callable wrapper around the numpy MA-INBL reference implementation.
    Always available regardless of torch/triton installation.
    """

    def __call__(
        self,
        x: np.ndarray,
        wq_packed: np.ndarray,
        wk_packed: np.ndarray,
        wv_packed: np.ndarray,
        w_scale: float,
        ors_mat: np.ndarray,
        **kwargs,
    ) -> tuple[np.ndarray, dict]:
        return ma_inbl_attention_np(
            x, wq_packed, wk_packed, wv_packed, w_scale, ors_mat, **kwargs
        )

    @property
    def available(self) -> bool:
        return True


# ── Triton kernel (requires torch + triton) ────────────────────────────────────

try:
    import torch
    import triton
    import triton.language as tl

    @triton.jit
    def _sw_popcount_tl(x):
        """Hamming weight for a 32-bit integer — Triton JIT helper."""
        x = x - ((x >> 1) & 0x55555555)
        x = (x & 0x33333333) + ((x >> 2) & 0x33333333)
        x = (x + (x >> 4)) & 0x0F0F0F0F
        return (x * 0x01010101) >> 24

    @triton.jit
    def _binary_linear_packed(
        x_ptr, w_ptr, out_ptr,
        M, N, D,
        N_WORDS: tl.constexpr,
        BLOCK_M: tl.constexpr,
        BLOCK_N: tl.constexpr,
    ):
        """
        XNOR+popcount binary matmul tile.

        x_ptr   : [M, N_WORDS] uint32  packed binarised activations
        w_ptr   : [N, N_WORDS] uint32  packed binarised weights
        out_ptr : [M, N]       int32   bipolar = 2*popcount(xnor) - D
        """
        pid_m = tl.program_id(0)
        pid_n = tl.program_id(1)
        offs_m = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
        offs_n = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
        m_mask = offs_m < M
        n_mask = offs_n < N

        acc = tl.zeros((BLOCK_M, BLOCK_N), dtype=tl.int32)
        for w in tl.static_range(N_WORDS):
            x_words = tl.load(
                x_ptr + offs_m * N_WORDS + w, mask=m_mask, other=0
            )
            w_words = tl.load(
                w_ptr + offs_n * N_WORDS + w, mask=n_mask, other=0
            )
            # Broadcast XNOR: [BLOCK_M, 1] xnor [1, BLOCK_N]
            xnor = ~(x_words[:, None] ^ w_words[None, :])
            acc = acc + _sw_popcount_tl(xnor)

        bipolar = 2 * acc - D
        out_offs = offs_m[:, None] * N + offs_n[None, :]
        out_mask = m_mask[:, None] & n_mask[None, :]
        tl.store(out_ptr + out_offs, bipolar, mask=out_mask)

    @triton.jit
    def ma_inbl_attention_kernel(
        # Inputs
        x_ptr,           # [B, S, D]      float16
        wq_ptr,          # [H, Dh, Dh]    float16  binary ±1
        wk_ptr,
        wv_ptr,
        mag_scale_ptr,   # [1]             float32  global magnitude scale
        ors_ptr,         # [H, Dh, Dh]    float32  orthogonal per head
        # Output
        out_ptr,         # [B, S, D]      float16
        # Dimensions
        B, S, D,
        H: tl.constexpr,
        Dh: tl.constexpr,
        N_INT4: tl.constexpr,
        # Hyperparameters
        TEMPERATURE: tl.constexpr,
        BINARY_RATIO: tl.constexpr,
        TRAINING_BINARY_RATIO: tl.constexpr,
        MAX_GROWTH: tl.constexpr,
        BLOCK_S: tl.constexpr,
    ):
        """
        Fused MA-INBL attention kernel (one program per batch × head × S-block).

        Note: uses ±1 float binary weights via tl.dot (equivalent to the
        XNOR+popcount path but runnable without the _binary_linear_packed grid).
        A production implementation would call _binary_linear_packed separately.
        """
        batch_id = tl.program_id(0)
        head_id  = tl.program_id(1)
        block_id = tl.program_id(2)

        offs_s = block_id * BLOCK_S + tl.arange(0, BLOCK_S)
        offs_d = tl.arange(0, Dh)
        s_mask = offs_s < S
        d_mask = offs_d < Dh

        x_base = x_ptr + batch_id * S * D + head_id * Dh

        # ── Load x tile [BLOCK_S, Dh] ────────────────────────────────────────
        x_tile = tl.load(
            x_base + offs_s[:, None] * D + offs_d[None, :],
            mask=s_mask[:, None] & d_mask[None, :], other=0.0,
        ).to(tl.float32)

        # ── MA decomposition: magnitude + unit direction ──────────────────────
        mag_sq = tl.sum(x_tile * x_tile, axis=1)             # [BLOCK_S]
        mag    = tl.sqrt(mag_sq + 1e-8)
        mag_scale = tl.load(mag_scale_ptr)
        mag_q  = tl.minimum(
            tl.cast(tl.floor(mag / (mag_scale + 1e-8) + 0.5), tl.int32),
            N_INT4 - 1,
        )
        mag_dequant = tl.cast(mag_q, tl.float32) * mag_scale  # [BLOCK_S]
        direction   = x_tile / (mag[:, None] + 1e-8)          # [BLOCK_S, Dh]

        # Binarise direction to ±1 float (equivalent to packed XNOR path)
        dir_bin = tl.where(direction > 0.0, 1.0, -1.0).to(tl.float16)

        # ── Load weight tiles for this head ──────────────────────────────────
        w_off = head_id * Dh * Dh + offs_d[:, None] * Dh + offs_d[None, :]
        w_mask = d_mask[:, None] & d_mask[None, :]
        wq = tl.load(wq_ptr + w_off, mask=w_mask, other=0.0).to(tl.float16)
        wk = tl.load(wk_ptr + w_off, mask=w_mask, other=0.0).to(tl.float16)
        wv = tl.load(wv_ptr + w_off, mask=w_mask, other=0.0).to(tl.float16)

        # ── Q, K, V projections ───────────────────────────────────────────────
        scale = mag_dequant / tl.cast(Dh, tl.float32)         # [BLOCK_S]
        Q_tile = tl.dot(dir_bin, wq).to(tl.float32) * scale[:, None]
        K_tile = tl.dot(dir_bin, wk).to(tl.float32) * scale[:, None]
        V_tile = tl.dot(dir_bin, wv).to(tl.float32) * scale[:, None]

        # ── Dual-scale factor ─────────────────────────────────────────────────
        if BINARY_RATIO == 1.0:
            dual_scale = TRAINING_BINARY_RATIO * TRAINING_BINARY_RATIO
        else:
            dual_scale = 1.0

        # ── Numerically stable softmax attention ──────────────────────────────
        inv_sqrt = 1.0 / tl.sqrt(tl.cast(Dh, tl.float32))
        scores = tl.dot(Q_tile.to(tl.float16), tl.trans(K_tile.to(tl.float16))).to(tl.float32)
        scores = scores * (inv_sqrt * dual_scale / TEMPERATURE)
        scores_max = tl.max(scores, axis=1)[:, None]
        scores = scores - scores_max
        ew = tl.exp(scores)
        attn_w = ew / (tl.sum(ew, axis=1)[:, None] + 1e-8)
        O_tile = tl.dot(attn_w.to(tl.float16), V_tile.to(tl.float16)).to(tl.float32)

        # ── MGC ───────────────────────────────────────────────────────────────
        candidate = x_tile + O_tile
        cand_sq   = tl.sum(candidate * candidate, axis=1)
        cand_mag  = tl.sqrt(cand_sq + 1e-8)
        x_mag     = tl.sqrt(mag_sq + 1e-8)
        max_allowed = x_mag * (1.0 + MAX_GROWTH)
        mgc_scale = tl.where(cand_mag > max_allowed, max_allowed / cand_mag, 1.0)
        clamped   = candidate * mgc_scale[:, None]

        # ── ORS ───────────────────────────────────────────────────────────────
        ors = tl.load(
            ors_ptr + head_id * Dh * Dh + offs_d[:, None] * Dh + offs_d[None, :],
            mask=w_mask, other=0.0,
        ).to(tl.float32)
        O_delta = clamped - x_tile
        rotated = tl.dot(O_delta.to(tl.float16), ors.to(tl.float16)).to(tl.float32)
        output  = x_tile + rotated

        if BINARY_RATIO == 1.0:
            output = output * TRAINING_BINARY_RATIO

        # ── Store ─────────────────────────────────────────────────────────────
        out_base = out_ptr + batch_id * S * D + head_id * Dh
        tl.store(
            out_base + offs_s[:, None] * D + offs_d[None, :],
            output.to(tl.float16),
            mask=s_mask[:, None] & d_mask[None, :],
        )

    class MA_INBLAttentionKernelTriton:
        """
        Callable wrapper around the Triton MA-INBL attention kernel.

        Accepts packed uint32 weights (output of pack_bits_np) plus the
        ORS matrix and dispatches to the fused Triton kernel.

        Call signature (matches MA_INBLAttentionKernelNP):
            kernel(x, wq_packed, wk_packed, wv_packed, w_scale, ors_mat, **kwargs)

        x          : [S, D]          float32 numpy
        wq_packed  : [D, D//32]      uint32  numpy (from pack_bits_np)
        ors_mat    : [H, Dh, Dh]     float32 numpy
        Returns    : (output [S, D] float32, telemetry dict)
        """

        def __call__(
            self,
            x: np.ndarray,
            wq_packed: np.ndarray,
            wk_packed: np.ndarray,
            wv_packed: np.ndarray,
            w_scale: float,
            ors_mat: np.ndarray,
            *,
            n_heads: int = 8,
            temperature: float = 1.0,
            binary_ratio: float = 0.0,
            training_binary_ratio: float = 1.0,
            max_growth: float = 0.5,
            n_int4: int = 16,
            block_size_l: int = 16,
            block_size_dh: int = 8,
            **_kw,
        ) -> tuple[np.ndarray, dict]:
            device = "cuda"
            S, D = x.shape
            H = n_heads
            Dh = D // H
            BLOCK_S = min(block_size_l, S)

            # ── 1. Device allocation ──────────────────────────────────────────
            buffers = prepare_qkv_device(
                wq_packed, wk_packed, wv_packed, ors_mat, x, device=device
            )
            x_dev   = buffers["x_dev"].float()            # [1, S, D]
            wq_dev  = buffers["wq_dev"]                   # [D, n_words] int32
            wk_dev  = buffers["wk_dev"]
            wv_dev  = buffers["wv_dev"]
            ors_dev = buffers["ors_dev"]                  # [H, Dh, Dh]
            mag_scale = buffers["mag_scale"]

            ms_t  = torch.tensor([mag_scale], dtype=torch.float32, device=device)
            out_t = torch.zeros_like(x_dev)               # [1, S, D]

            # ── 2. Launch grid: (batch=1, head, S-tiles) ─────────────────────
            n_blocks_s = (S + BLOCK_S - 1) // BLOCK_S
            grid = (1, H, n_blocks_s)

            # Convert packed int32 weights to float16 ±1 for fused kernel
            # (reinterpret uint32 bits back to ±1 sign for tl.dot path)
            def _packed_to_pm1(wpk: "torch.Tensor", D: int, H: int, Dh: int) -> "torch.Tensor":
                # Unpack D bits per row → ±1 float16, reshape [H, Dh, Dh]
                N_WORDS = (D + 31) // 32
                pm1 = torch.zeros(D, D, dtype=torch.float16, device=wpk.device)
                for b in range(32):
                    bit_col = b
                    word_col = 0
                    # extract each bit position across all n_words
                    for wrd in range(N_WORDS):
                        col = wrd * 32 + b
                        if col >= D:
                            break
                        bits = (wpk[:, wrd] >> b) & 1
                        pm1[:, col] = (bits.to(torch.float32) * 2 - 1).to(torch.float16)
                return pm1.reshape(H, Dh, D).permute(0, 2, 1)[:, :Dh, :].contiguous()

            wq_t = _packed_to_pm1(wq_dev, D, H, Dh)  # [H, Dh, Dh]
            wk_t = _packed_to_pm1(wk_dev, D, H, Dh)
            wv_t = _packed_to_pm1(wv_dev, D, H, Dh)

            x_half = x_dev.half()
            ma_inbl_attention_kernel[grid](
                x_half, wq_t, wk_t, wv_t, ms_t, ors_dev, out_t,
                1, S, D,
                H=H,
                Dh=Dh,
                N_INT4=n_int4,
                TEMPERATURE=temperature,
                BINARY_RATIO=binary_ratio,
                TRAINING_BINARY_RATIO=training_binary_ratio,
                MAX_GROWTH=max_growth,
                BLOCK_S=BLOCK_S,
            )
            torch.cuda.synchronize()

            # ── 4. Return output + telemetry ──────────────────────────────────
            output = out_t.squeeze(0).float().cpu().numpy()
            x_mag   = float(np.linalg.norm(x, axis=-1).mean())
            out_mag = float(np.linalg.norm(output, axis=-1).mean())
            dual_scale = (training_binary_ratio ** 2) if binary_ratio == 1.0 else 1.0
            telemetry = {
                "binary_ratio"     : float(binary_ratio),
                "dual_scale"       : float(dual_scale),
                "mean_attn_entropy": 0.0,
                "mgc_scale_mean"   : 1.0,
                "cand_mag_mean"    : out_mag,
                "x_mag_mean"       : x_mag,
                "backend"          : "triton",
            }
            return output, telemetry

        @property
        def available(self) -> bool:
            return True

    TRITON_AVAILABLE = True

except ImportError:
    class MA_INBLAttentionKernelTriton:  # type: ignore[no-redef]
        """Stub — triton/torch not installed."""

        def __call__(self, *args, **kwargs) -> tuple:
            raise RuntimeError(
                "Triton is not available. "
                "Install triton to use the GPU kernel."
            )

        @property
        def available(self) -> bool:
            return False

    TRITON_AVAILABLE = False
