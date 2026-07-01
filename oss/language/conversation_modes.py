"""
Binary conversational mode codes.

Each mode is a B-bit binary vector that encodes GH05T3's current
conversational posture.  Modes are injected into MA-INBL attention
alongside token features so heads can specialise per mode.

Built-in modes (8-bit):
    technical     — 10001000  precise, low entropy
    exploratory   — 01010100  curious, divergent
    loyal_stable  — 11001100  conservative, high consistency
    innovative    — 00110110  high temperature, ORS diversity
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np


@dataclass
class ModeConfig:
    code_bits: int = 8


# Default 8-bit mode definitions (MSB → LSB ordering by convention)
_DEFAULT_MODES: Dict[str, list[int]] = {
    "technical":    [1, 0, 0, 0, 1, 0, 0, 0],
    "exploratory":  [0, 1, 0, 1, 0, 1, 0, 0],
    "loyal_stable": [1, 1, 0, 0, 1, 1, 0, 0],
    "innovative":   [1, 0, 1, 1, 0, 1, 1, 0],
}


class ConversationModes:
    """
    Registry of named binary mode vectors.

    Provides broadcast-compatible codes for injection into attention:
        mode_code = modes.code_for_mode("technical")  # [code_bits] float32
    """

    def __init__(self, cfg: ModeConfig | None = None) -> None:
        self.cfg = cfg or ModeConfig()
        self.modes: Dict[str, np.ndarray] = {}
        self._init_default_modes()

    def _init_default_modes(self) -> None:
        b = self.cfg.code_bits
        for name, vec in _DEFAULT_MODES.items():
            padded = (vec + [0] * b)[:b]
            self.modes[name] = np.array(padded, dtype=np.float32)

    def code_for_mode(self, name: str) -> np.ndarray:
        """Return the [code_bits] binary vector for a named mode."""
        return self.modes.get(name, np.zeros(self.cfg.code_bits, dtype=np.float32))

    def register_mode(self, name: str, code: np.ndarray) -> None:
        """Add or replace a named mode vector (genome-driven extension hook)."""
        self.modes[name] = code.astype(np.float32)[: self.cfg.code_bits]

    def inject_into_sequence(self, x: np.ndarray, mode_name: str) -> np.ndarray:
        """
        Concatenate mode code onto the last dimension of x.

        x         : [..., D] float32
        Returns   : [..., D + code_bits] float32
        """
        code = self.code_for_mode(mode_name)
        broadcast = np.broadcast_to(code, x.shape[:-1] + (self.cfg.code_bits,))
        return np.concatenate([x, broadcast.astype(np.float32)], axis=-1)

    def list_modes(self) -> list[str]:
        return list(self.modes.keys())
