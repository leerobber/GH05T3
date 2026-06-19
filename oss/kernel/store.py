"""Persist civilization kernel state."""
from __future__ import annotations

import json
import time
from pathlib import Path

from oss.kernel.schemas import KernelState, TickResult
from oss.kernel.state_machines import CycleMachineState
from oss.kernel.training_schedule import TrainingProgress

_REPO = Path(__file__).resolve().parents[2]
STATE_PATH = _REPO / "data" / "kernel_state.json"
LOG_PATH = _REPO / "data" / "kernel_ticks.jsonl"
TRAINING_PATH = _REPO / "data" / "kernel_training.json"
CYCLE_PATH = _REPO / "data" / "kernel_cycle.json"
CYCLE_LOG_PATH = _REPO / "data" / "kernel_cycle_log.jsonl"


def load_state() -> KernelState:
    if not STATE_PATH.exists():
        return KernelState()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return KernelState.from_dict(data)
    except Exception:
        return KernelState()


def save_state(state: KernelState) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")


def append_tick_log(result: TickResult) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {**result.to_dict(), "ts": time.time()}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def load_training_progress() -> TrainingProgress:
    if not TRAINING_PATH.exists():
        return TrainingProgress(started_ts=time.time())
    try:
        data = json.loads(TRAINING_PATH.read_text(encoding="utf-8"))
        return TrainingProgress.from_dict(data)
    except Exception:
        return TrainingProgress(started_ts=time.time())


def save_training_progress(progress: TrainingProgress) -> None:
    TRAINING_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRAINING_PATH.write_text(json.dumps(progress.to_dict(), indent=2), encoding="utf-8")


def load_cycle_state() -> CycleMachineState:
    if not CYCLE_PATH.exists():
        return CycleMachineState()
    try:
        data = json.loads(CYCLE_PATH.read_text(encoding="utf-8"))
        return CycleMachineState.from_dict(data)
    except Exception:
        return CycleMachineState()


def save_cycle_state(state: CycleMachineState) -> None:
    CYCLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CYCLE_PATH.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")


def append_cycle_log(entry: dict[str, Any]) -> None:
    CYCLE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {**entry, "ts": time.time()}
    with open(CYCLE_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")