"""OSS attention sub-package — MA-INBL fused attention kernel."""
from oss.attention.kernel import (
    TRITON_AVAILABLE,
    MA_INBLAttentionKernelNP,
    MA_INBLAttentionKernelTriton,
    binary_matmul_np,
    ma_inbl_attention_np,
    ma_inbl_np,
    pack_bits_np,
    sw_popcount_np,
    sw_popcount_np_vec,
)
from oss.attention.attention import MA_INBLAttention
from oss.attention.telemetry import AttentionTelemetrySink

__all__ = [
    "TRITON_AVAILABLE",
    "MA_INBLAttentionKernelNP",
    "MA_INBLAttentionKernelTriton",
    "MA_INBLAttention",
    "AttentionTelemetrySink",
    "ma_inbl_attention_np",
    "ma_inbl_np",
    "binary_matmul_np",
    "pack_bits_np",
    "sw_popcount_np",
    "sw_popcount_np_vec",
]
