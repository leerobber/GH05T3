"""MA_INBLAttention — high-level module wrapping the MA-INBL kernel."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from oss.quantization.binary_quant import BinaryQuantizer

from oss.attention.kernel import (
    TRITON_AVAILABLE,
    MA_INBLAttentionKernelTriton,
    ma_inbl_attention_np,
    pack_bits_np,
)


class MA_INBLAttention:
    """
    Multi-head attention using MA-INBL binary projections, MGC, and ORS.

    Uses the numpy reference implementation (Triton available via TRITON_AVAILABLE flag).

    Parameters
    ----------
    d_model / embed_dim   : total model dimension (must be divisible by n_heads)
    n_heads / num_heads   : number of attention heads
    training_binary_ratio : scale factor stored for dual-scale bookkeeping;
                            dual-scale activation requires passing binary_ratio=1.0
                            to ma_inbl_attention_np directly (not via this class).
    temperature           : softmax temperature (lower → sharper)
    max_growth            : MGC threshold — max relative magnitude increase allowed
    n_int4                : INT4 quantisation levels for magnitude (default 16)
    w_scale               : weight scale factor applied to binary projection output
    ors_matrix            : optional external orthogonal matrix:
                              - [n_heads, head_dim, head_dim] → used directly
                              - [embed_dim, embed_dim]        → split into per-head blocks
                              - None → generated via QR internally (requires seed)
    seed                  : RNG seed for weight and ORS initialisation
    """

    def __init__(
        self,
        d_model: int | None = None,
        n_heads: int | None = None,
        *,
        # New-API aliases
        embed_dim: int | None = None,
        num_heads: int | None = None,
        training_binary_ratio: float = 1.0,
        temperature: float = 1.0,
        max_growth: float = 0.5,
        n_int4: int = 16,
        w_scale: float = 1.0,
        ors_matrix: np.ndarray | None = None,
        seed: int = 42,
        # Old-API extra params kept for backward compat
        binary_ratio: float = 0.0,
        # Backend selection: "auto" | "numpy" | "triton"
        backend: str = "auto",
        # Optional quantizer — if set, _project() uses it for float projections
        quantizer: "BinaryQuantizer | None" = None,
    ) -> None:
        resolved_d = d_model if d_model is not None else (embed_dim if embed_dim is not None else 256)
        resolved_h = n_heads if n_heads is not None else (num_heads if num_heads is not None else 8)

        if resolved_d % resolved_h != 0:
            raise ValueError(f"d_model={resolved_d} must be divisible by n_heads={resolved_h}")

        self.d_model = resolved_d
        self.n_heads = resolved_h
        self.head_dim = resolved_d // resolved_h
        # binary_ratio=0.0 by default so dual-scale never activates at class level;
        # call ma_inbl_attention_np directly with binary_ratio=1.0 to test that path.
        self.binary_ratio = binary_ratio
        self.training_binary_ratio = training_binary_ratio
        self.temperature = temperature
        self.max_growth = max_growth
        self.n_int4 = n_int4
        self.w_scale = w_scale
        self.quantizer = quantizer

        # Backend selection
        if backend == "triton" and not TRITON_AVAILABLE:
            raise RuntimeError(
                "backend='triton' requested but Triton is not installed."
            )
        self.backend: str = backend
        self._use_triton: bool = (
            backend == "triton" or (backend == "auto" and TRITON_AVAILABLE)
        )
        self._triton_kernel: MA_INBLAttentionKernelTriton | None = (
            MA_INBLAttentionKernelTriton() if self._use_triton else None
        )

        rng = np.random.default_rng(seed)

        def _init_w() -> tuple[np.ndarray, np.ndarray]:
            w = rng.choice([-1.0, 1.0], size=(resolved_d, resolved_d)).astype(np.float32)
            return w, pack_bits_np(w)

        self._wq, self._wq_packed = _init_w()
        self._wk, self._wk_packed = _init_w()
        self._wv, self._wv_packed = _init_w()

        # ORS matrix setup
        if ors_matrix is not None:
            ors = np.asarray(ors_matrix, dtype=np.float32)
            if ors.shape == (resolved_h, self.head_dim, self.head_dim):
                self._ors_mat = ors
            elif ors.shape == (resolved_d, resolved_d):
                # Extract per-head diagonal blocks
                per_head = np.zeros((resolved_h, self.head_dim, self.head_dim), dtype=np.float32)
                for h in range(resolved_h):
                    s = h * self.head_dim
                    per_head[h] = ors[s : s + self.head_dim, s : s + self.head_dim]
                self._ors_mat = per_head
            else:
                raise ValueError(
                    f"ors_matrix shape {ors.shape} not supported; expected "
                    f"({resolved_h}, {self.head_dim}, {self.head_dim}) or "
                    f"({resolved_d}, {resolved_d})"
                )
        else:
            ors = np.zeros((resolved_h, self.head_dim, self.head_dim), dtype=np.float32)
            for h in range(resolved_h):
                M = rng.standard_normal((self.head_dim, self.head_dim)).astype(np.float32)
                Q, _ = np.linalg.qr(M)
                ors[h] = Q
            self._ors_mat = ors

    # ------------------------------------------------------------------
    def _project(self, x: np.ndarray, W: np.ndarray) -> np.ndarray:
        """
        Linear projection with optional quantization.

        When self.quantizer is set the projection uses BinaryQuantizer.matmul()
        (addition-only, ternary/binary weights).  Without a quantizer it falls
        back to a plain float32 matmul — identical to the packed-bit path but
        expressed as a float multiply for simplicity here.

        x : [..., d_model]
        W : [d_model, d_model] float32
        Returns : [..., d_model]
        """
        if self.quantizer is not None:
            W_q, W_scale = self.quantizer.quantize_weights(W)
            x_q, x_scale = self.quantizer.quantize_activations(x)
            return self.quantizer.matmul(x_q, W_q, W_scale) * x_scale
        return x @ W

    # ------------------------------------------------------------------
    def forward(self, x: np.ndarray) -> tuple[np.ndarray, dict]:
        """
        Forward pass.

        x : [seq_len, d_model], [batch, seq_len, d_model], or
            [batch, seq_len, embed_dim] (all equivalent)
        Returns (output same shape as x, telemetry_dict)
        """
        if x.ndim == 2:
            if self._use_triton:
                return self._forward_triton(x)
            return self._forward_numpy(x)

        if x.ndim == 3:
            outputs, tels = [], []
            for sample in x:
                o, t = self.forward(sample)
                outputs.append(o)
                tels.append(t)
            avg_tel = {k: float(np.mean([t[k] for t in tels])) for k in tels[0]}
            return np.stack(outputs, axis=0), avg_tel

        raise ValueError(f"Expected 2-D or 3-D input, got shape {x.shape}")

    def _forward_numpy(self, x: np.ndarray) -> tuple[np.ndarray, dict]:
        """Run the numpy reference implementation."""
        return ma_inbl_attention_np(
            x,
            self._wq_packed,
            self._wk_packed,
            self._wv_packed,
            self.w_scale,
            self._ors_mat,
            n_heads=self.n_heads,
            temperature=self.temperature,
            binary_ratio=self.binary_ratio,
            training_binary_ratio=self.training_binary_ratio,
            max_growth=self.max_growth,
            n_int4=self.n_int4,
        )

    def _forward_triton(self, x: np.ndarray) -> tuple[np.ndarray, dict]:
        """Run the Triton GPU kernel (falls back to numpy if unavailable)."""
        if self._triton_kernel is None or not self._triton_kernel.available:
            return self._forward_numpy(x)

        return self._triton_kernel(
            x.astype(np.float32),
            self._wq_packed,
            self._wk_packed,
            self._wv_packed,
            self.w_scale,
            self._ors_mat,
            n_heads=self.n_heads,
            temperature=self.temperature,
            binary_ratio=self.binary_ratio,
            training_binary_ratio=self.training_binary_ratio,
            max_growth=self.max_growth,
            n_int4=self.n_int4,
        )

    # ------------------------------------------------------------------
    @property
    def active_backend(self) -> str:
        """Resolved backend name: 'triton' or 'numpy'."""
        return "triton" if self._use_triton else "numpy"

    # ------------------------------------------------------------------
    def state_dict(self) -> dict:
        return {
            "d_model": self.d_model,
            "n_heads": self.n_heads,
            "head_dim": self.head_dim,
            "binary_ratio": self.binary_ratio,
            "training_binary_ratio": self.training_binary_ratio,
            "temperature": self.temperature,
            "max_growth": self.max_growth,
            "n_int4": self.n_int4,
            "w_scale": self.w_scale,
            "triton_available": TRITON_AVAILABLE,
            "backend": self.backend,
            "active_backend": self.active_backend,
        }
