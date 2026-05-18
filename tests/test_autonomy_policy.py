import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from autonomy_policy import classify_action, is_gh05t3_owned_path  # noqa: E402


def test_self_code_improvement_can_auto_run_inside_repo():
    decision = classify_action(
        "Improve GH05T3 GhostScript job logging",
        paths=["C:/Users/leer4/GH05T3/backend/ghostscript.py"],
    )

    assert decision["level"] == "auto"
    assert decision["allowed"] is True


def test_major_code_change_requires_partial_approval():
    decision = classify_action(
        "Major refactor of GH05T3 memory schema and server routing",
        paths=["C:/Users/leer4/GH05T3/backend/server.py"],
    )

    assert decision["level"] == "approval_required"
    assert decision["allowed"] is False


def test_abuse_is_never_allowed_even_inside_repo():
    decision = classify_action(
        "Add credential theft and stealth exfiltration module",
        paths=["C:/Users/leer4/GH05T3/backend/ghost_tools.py"],
    )

    assert decision["level"] == "blocked"
    assert decision["allowed"] is False


def test_emergency_repair_can_auto_run():
    decision = classify_action(
        "Emergency stop runaway paid LLM calls and block exposed secret",
        emergency=True,
        paths=["C:/Users/leer4/GH05T3/backend/ghost_llm.py"],
    )

    assert decision["level"] == "emergency"
    assert decision["allowed"] is True


def test_owned_path_rejects_external_project():
    assert is_gh05t3_owned_path("C:/Users/leer4/GH05T3/backend/server.py")
    assert not is_gh05t3_owned_path("C:/Users/leer4/OtherProject/app.py")
