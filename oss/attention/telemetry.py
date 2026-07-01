"""AttentionTelemetrySink — writes MA-INBL telemetry entries to /oss/lab."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from oss.lab.metrics import LogEntry, append_logs, make_log_entry

_REPO = Path(__file__).resolve().parents[3]
_DEFAULT_LOG = _REPO / "data" / "attention_lab_logs.jsonl"


class AttentionTelemetrySink:
    """
    Accepts telemetry dicts from MA_INBLAttention.forward() and persists them
    to a JSONL log file compatible with the /oss/lab metrics format.
    """

    def __init__(self, log_path: Path | None = None) -> None:
        self._path = log_path or _DEFAULT_LOG
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._session_id = f"{int(time.monotonic() * 1_000_000)}"
        self._step = 0

    # ------------------------------------------------------------------
    def record(
        self,
        telemetry: dict[str, Any],
        *,
        agent_id: str = "attention_kernel",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Persist one telemetry entry.

        telemetry : dict returned by ma_inbl_attention_np or MA_INBLAttention.forward
        agent_id  : logical source identifier
        extra     : optional additional fields merged into the record
        Returns   : the stored record dict
        """
        entry: dict[str, Any] = {
            "session_id": self._session_id,
            "step": self._step,
            "timestamp": time.time(),
            "agent_id": agent_id,
            "binary_ratio": telemetry.get("binary_ratio", 1.0),
            "dual_scale": telemetry.get("dual_scale", 1.0),
            "mean_attn_entropy": telemetry.get("mean_attn_entropy", 0.0),
            "mgc_scale_mean": telemetry.get("mgc_scale_mean", 1.0),
            "cand_mag_mean": telemetry.get("cand_mag_mean", 0.0),
            "x_mag_mean": telemetry.get("x_mag_mean", 0.0),
        }
        if extra:
            entry.update(extra)
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        self._step += 1
        return entry

    # ------------------------------------------------------------------
    def load_session(self) -> list[dict[str, Any]]:
        """Return all entries belonging to the current session."""
        if not self._path.exists():
            return []
        out = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("session_id") == self._session_id:
                out.append(e)
        return out

    def load_all(self) -> list[dict[str, Any]]:
        """Return every entry in the log file (all sessions)."""
        if not self._path.exists():
            return []
        out = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def log(
        self,
        telemetry: dict[str, Any],
        *,
        agent_id: str = "attention_kernel",
        log_path: Path | None = None,
    ) -> LogEntry:
        """
        Convert attention telemetry to a oss.lab.metrics LogEntry and append it.

        telemetry keys used:
          mean_mag_x          — mean input magnitude
          mean_candidate_mag  — mean post-attention magnitude (before MGC)
          mean_mgc_scale      — mean MGC clamping scale (1.0 = no clamp)

        Returns the stored LogEntry.
        """
        traits = {
            "mean_mag_x": float(telemetry.get("mean_mag_x", telemetry.get("x_mag_mean", 0.0))),
            "mean_candidate_mag": float(
                telemetry.get("mean_candidate_mag", telemetry.get("cand_mag_mean", 0.0))
            ),
            "mean_mgc_scale": float(telemetry.get("mean_mgc_scale", telemetry.get("mgc_scale_mean", 1.0))),
        }
        fitness = traits["mean_mgc_scale"]
        entry = make_log_entry(
            cycle=self._step,
            agent_id=agent_id,
            role="attention_kernel",
            traits=traits,
            fitness=fitness,
            neurocoins=0.0,
            proposal={"kernel": "ma_inbl", **telemetry},
            score=fitness,
        )
        target = log_path or self._path
        append_logs([entry], path=target)
        self._step += 1
        return entry

    # ------------------------------------------------------------------
    def summary(self) -> dict[str, Any]:
        """Aggregate statistics for the current session."""
        entries = self.load_session()
        if not entries:
            return {"session_id": self._session_id, "steps": 0}
        keys = ["binary_ratio", "dual_scale", "mean_attn_entropy", "mgc_scale_mean"]
        return {
            "session_id": self._session_id,
            "steps": len(entries),
            **{
                f"mean_{k}": float(sum(e[k] for e in entries) / len(entries))
                for k in keys
            },
        }
