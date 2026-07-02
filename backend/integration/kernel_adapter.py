"""Glue layer between GH05T3 expert agents and the sovereign-core Python Runtime.

KernelAdapter always uses the pure-Python sovereign-core Runtime because
expert agents extend Agent and rely on its inbox/state-machine API.

The Rust sovereign_core_rs backend is used by KernelBridge (HyperAgents)
for block-level dispatch via WASM agents — those two runtimes have different
interfaces and serve different purposes.

Set SOVEREIGN_CORE_PATH=/path/to/sovereign-core to locate the Python package.
sovereign_core_rs (Rust) is detected here only for informational purposes.
"""
from __future__ import annotations

import sys
import os

# Detect whether the Rust extension is available (for status reporting).
try:
    import sovereign_core_rs as _scrs  # type: ignore[import]
    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False

# Python sovereign-core — required for expert agent step() loop.
_SOVEREIGN_PATH = os.environ.get("SOVEREIGN_CORE_PATH", "")
if _SOVEREIGN_PATH and _SOVEREIGN_PATH not in sys.path:
    sys.path.insert(0, _SOVEREIGN_PATH)

from src.kernel.runtime import Runtime
from src.isa.instruction import Instruction
from src.isa.opcodes import Opcode
from src.semantics.semantic_word import SemanticWord, WordType, IntentType, ChannelType


class KernelAdapter:
    """Wraps sovereign-core Python Runtime for GH05T3 expert agents.

    Uses the Python Runtime's inbox/state-machine API.
    For block-level Rust+WASM dispatch use KernelBridge (hyper/kernel_bridge.py).
    """

    rust_backend: bool = False  # KernelAdapter always uses Python Runtime

    def __init__(self) -> None:
        self.runtime = Runtime()
        self._agent_roles: dict[int, str] = {}

    # ── agent lifecycle ──────────────────────────────────────────────────────

    def spawn(self, role: str) -> int:
        agent_id = self.runtime.spawn_agent()
        self._agent_roles[agent_id] = role
        return agent_id

    def kill(self, agent_id: int) -> None:
        self.runtime.kill_agent(agent_id)
        self._agent_roles.pop(agent_id, None)

    def role_of(self, agent_id: int) -> str:
        return self._agent_roles.get(agent_id, "unknown")

    # ── encoding helpers ─────────────────────────────────────────────────────

    @staticmethod
    def encode(
        intent: IntentType = IntentType.NONE,
        word_type: WordType = WordType.CONTROL,
        channel: ChannelType = ChannelType.INTERNAL,
        priority: int = 128,
        confidence: float = 1.0,
        payload_ref: int = 0,
    ) -> int:
        return SemanticWord.make(
            type=word_type,
            intent=intent,
            channel=channel,
            priority=priority,
            confidence=confidence,
            payload_ref=payload_ref,
        ).encode()

    @staticmethod
    def decode(word_int: int) -> SemanticWord:
        return SemanticWord.decode(word_int)

    # ── dispatch helpers ─────────────────────────────────────────────────────

    def send(self, sender_id: int, receiver_id: int, word_int: int) -> None:
        self.runtime.route_message(sender_id, receiver_id, word_int)

    def broadcast(self, sender_id: int, word_int: int) -> None:
        self.runtime.broadcast(sender_id, word_int)

    def dispatch(self, agent_id: int, opcode: Opcode, args: list[int] | None = None) -> list[int]:
        instr = Instruction(opcode=opcode, args=args or [])
        return self.runtime.dispatch_instruction(agent_id, instr)

    # ── payload store ────────────────────────────────────────────────────────

    def store(self, obj: object) -> int:
        return self.runtime.store_payload(obj)

    def load(self, ref: int) -> object:
        return self.runtime.get_payload(ref)

    # ── observability ────────────────────────────────────────────────────────

    def add_hook(self, fn) -> None:
        self.runtime.add_hook(fn)

    def status(self) -> dict:
        s = self.runtime.status()
        s["roles"] = dict(self._agent_roles)
        s["rust_available"] = _RUST_AVAILABLE
        return s
