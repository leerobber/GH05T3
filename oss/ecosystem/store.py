"""Persist OSS ecosystem FSM state."""
from __future__ import annotations

import json
import time
from pathlib import Path

from oss.ecosystem.fsm import EcosystemState

_REPO = Path(__file__).resolve().parents[2]
ECOSYSTEM_PATH = _REPO / "data" / "oss_ecosystem.json"
ECOSYSTEM_LOG_PATH = _REPO / "data" / "oss_ecosystem_log.jsonl"


def load_ecosystem_state() -> EcosystemState:
    if not ECOSYSTEM_PATH.exists():
        return EcosystemState()
    try:
        return EcosystemState.from_dict(json.loads(ECOSYSTEM_PATH.read_text(encoding="utf-8")))
    except Exception:
        return EcosystemState()


def save_ecosystem_state(state: EcosystemState) -> None:
    ECOSYSTEM_PATH.parent.mkdir(parents=True, exist_ok=True)
    ECOSYSTEM_PATH.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")


def append_ecosystem_log(entry: dict) -> None:
    ECOSYSTEM_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ECOSYSTEM_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({**entry, "ts": time.time()}) + "\n")