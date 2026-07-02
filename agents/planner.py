"""PlannerAgent — GH05T3 planner with GPU acceleration via UnifiedGpu."""
from __future__ import annotations

from typing import Any

try:
    from sovereign_gpu import UnifiedGpu
    _HAS_GPU = True
except ImportError:
    UnifiedGpu = None  # type: ignore[assignment,misc]
    _HAS_GPU = False


class PlannerAgent:
    """
    GH05T3 planner agent.

    reasoning_mode:
        "default"  — CPU/WASM planning via KernelBridge
        "gpu"      — GPU planner pipeline via UnifiedGpu
        "graph"    — GPU BFS/topo reasoning over a graph
        "gnn"      — GraphSAGE-Mean GNN embedding via UnifiedGpu
    """

    def __init__(
        self,
        reasoning_mode: str = "default",
        gpu_backend: str = "webgpu",
    ) -> None:
        self.reasoning_mode = reasoning_mode
        self.gpu: Any = None

        if _HAS_GPU and reasoning_mode in ("gpu", "graph", "gnn"):
            self.gpu = UnifiedGpu(backend=gpu_backend)

        # CSR + feature data for GNN mode — set via load_gnn_data()
        self._gnn_row_ptr:    list[int]   = []
        self._gnn_col_idx:    list[int]   = []
        self._gnn_node_feats: list[float] = []
        self._gnn_weight:     list[float] = []

    def load_graph(self, n_nodes: int, edges: list[tuple[int, int]]) -> None:
        """Load a graph for GPU graph-reasoning or GNN mode."""
        if self.gpu is not None:
            self.gpu.load_graph(n_nodes, edges)

    def load_gnn_data(
        self,
        row_ptr:    list[int],
        col_idx:    list[int],
        node_feats: list[float],
        weight:     list[float],
    ) -> None:
        """Store CSR + feature/weight arrays for GNN reasoning mode."""
        self._gnn_row_ptr    = row_ptr
        self._gnn_col_idx    = col_idx
        self._gnn_node_feats = node_feats
        self._gnn_weight     = weight

    def plan(self, block: bytes | dict | None = None) -> bytes | list[int] | None:
        """
        Execute the planner.

        Args:
            block: serialised KernelBlock bytes, dict of intent/payload, or None.

        Returns:
            - bytes: raw planner output (GPU path)
            - None:  CPU/WASM path — caller drives KernelBridge directly
        """
        if block is None:
            block = b""

        if isinstance(block, dict):
            block = str(block).encode()

        if self.reasoning_mode == "gpu" and self.gpu is not None:
            return self.gpu.plan(block)

        if self.reasoning_mode == "graph" and self.gpu is not None:
            # graph-reasoning: BFS from intent payload
            payload_ref = block[0] if block else 0
            return self.gpu.bfs(payload_ref)

        if self.reasoning_mode == "gnn" and self.gpu is not None:
            if not self._gnn_row_ptr:
                return None
            return self.gpu.embed(
                self._gnn_row_ptr,
                self._gnn_col_idx,
                self._gnn_node_feats,
                self._gnn_weight,
            )

        # CPU/WASM path — return None, caller uses KernelBridge
        return None

    def embed(
        self,
        row_ptr:    list[int],
        col_idx:    list[int],
        node_feats: list[float],
        weight:     list[float],
    ) -> list[float]:
        """GraphSAGE-Mean GNN: embed all nodes (GPU path only)."""
        if self.gpu is not None:
            return self.gpu.embed(row_ptr, col_idx, node_feats, weight)
        return []

    def status(self) -> dict:
        return {
            "reasoning_mode": self.reasoning_mode,
            "gpu_available":  self.gpu is not None,
            "gpu_backend":    self.gpu.backend if self.gpu else None,
            "planner_ready":  self.gpu.planner_ready() if self.gpu else False,
            "gnn_data_loaded": bool(self._gnn_row_ptr),
        }
