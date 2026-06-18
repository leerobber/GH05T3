"""Environment Layer runtime — in-memory session stubs for Phase 2 scaffold."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

DOMAINS = ("story_editor", "training", "frontier")


def list_domains() -> list[str]:
    """Return supported environment domains."""
    return list(DOMAINS)


@dataclass
class EnvironmentSession:
    session_id: str
    domain: str
    state: dict[str, Any] = field(default_factory=dict)


class EnvironmentRuntime:
    """In-memory environment loop — Phase 2 scaffold."""

    def __init__(self) -> None:
        self._sessions: dict[str, EnvironmentSession] = {}

    def start_session(
        self,
        domain: str,
        metadata: dict[str, Any] | None = None,
    ) -> EnvironmentSession:
        if domain not in DOMAINS:
            raise ValueError(f"Unknown domain: {domain}")
        session_id = str(uuid.uuid4())
        state: dict[str, Any] = {
            "metadata": dict(metadata or {}),
            "step": 0,
            "actions": [],
        }
        session = EnvironmentSession(session_id=session_id, domain=domain, state=state)
        self._sessions[session_id] = session
        return session

    def step(
        self,
        session_id: str,
        action: dict[str, Any] | None = None,
    ) -> EnvironmentSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found")
        session.state["step"] = int(session.state.get("step", 0)) + 1
        if action is not None:
            session.state.setdefault("actions", []).append(action)
        return session

    def snapshot(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found")
        return {
            "session_id": session.session_id,
            "domain": session.domain,
            "state": dict(session.state),
        }


_runtime: EnvironmentRuntime | None = None


def get_runtime() -> EnvironmentRuntime:
    global _runtime
    if _runtime is None:
        _runtime = EnvironmentRuntime()
    return _runtime