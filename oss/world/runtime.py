"""Environment Layer runtime — in-memory session stubs for Phase 2 scaffold."""
from __future__ import annotations

import importlib.util
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Awaitable, Callable

DOMAINS = ("story_editor", "training", "frontier")

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
_STORY_EDITOR_MODULE = "gh05t3_backend_integrations_story_editor"


def _load_story_editor() -> ModuleType:
    """Load backend story editor without colliding with repo-root integrations/."""
    cached = sys.modules.get(_STORY_EDITOR_MODULE)
    if cached is not None:
        return cached

    backend = str(_BACKEND.resolve())
    if backend not in sys.path:
        sys.path.insert(0, backend)

    module_path = _BACKEND / "integrations" / "story_editor.py"
    spec = importlib.util.spec_from_file_location(_STORY_EDITOR_MODULE, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load story editor module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_STORY_EDITOR_MODULE] = module
    spec.loader.exec_module(module)
    return module


def _stub_llm_call(_system: str, _messages: list[dict[str, str]]) -> str:
    """Placeholder LLM for tests and environments without a live model."""
    return "[Story editor LLM placeholder]"


async def _default_llm_call(system: str, messages: list[dict[str, str]]) -> str:
    return _stub_llm_call(system, messages)


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
        if domain == "story_editor":
            story_editor = _load_story_editor()
            story_editor.get_session(session_id)
            greeting = story_editor.story_editor_greeting()
            state["greeting"] = greeting
            state["last_reply"] = greeting
            state["story_editor_stage"] = 0
            state["story"] = {}
        session = EnvironmentSession(session_id=session_id, domain=domain, state=state)
        self._sessions[session_id] = session
        return session

    async def step(
        self,
        session_id: str,
        action: dict[str, Any] | None = None,
        llm_call: Callable[
            [str, list[dict[str, str]]],
            Awaitable[str],
        ] | None = None,
    ) -> EnvironmentSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found")
        session.state["step"] = int(session.state.get("step", 0)) + 1
        if action is not None:
            session.state.setdefault("actions", []).append(action)

        if session.domain == "story_editor":
            message = (action or {}).get("message")
            if not message:
                raise ValueError("story_editor step requires action.message")
            story_editor = _load_story_editor()
            call = llm_call or _default_llm_call
            turn_result = await story_editor.story_editor_turn(session_id, str(message), call)
            session.state["last_turn"] = turn_result
            session.state["last_reply"] = turn_result["reply"]
            session.state["story_editor_stage"] = turn_result["stage"]
            session.state["story"] = turn_result["story"]
            session.state["done"] = turn_result["done"]

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