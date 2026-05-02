#!/usr/bin/env python3
"""
GH05T3 Self-Improvement Engine — Supervised Mode
Scans codebase for dead code and proposes removals. Nothing is changed
without Robert's explicit approval. Run: python tools/self_improve.py
"""

import ast
import sys
import json
import difflib
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).parent.parent
STAGING_PATH = REPO_ROOT / "sandbox" / "experiments" / "pending_cleanup.json"
LOG_PATH = REPO_ROOT / "history" / "sessions" / "self_improve_log.jsonl"


# ── Dead Code Detection ────────────────────────────────────────────────────────

def collect_defined_names(tree: ast.Module) -> dict:
    """Return all top-level function/class/import names defined in a module."""
    defined = {"functions": [], "classes": [], "imports": []}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.col_offset == 0:  # top-level only
                defined["functions"].append(node.name)
        elif isinstance(node, ast.ClassDef) and node.col_offset == 0:
            defined["classes"].append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                defined["imports"].append(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                defined["imports"].append(alias.asname or alias.name)
    return defined


def find_all_usages(source: str, names: list) -> set:
    """Return which names from the list actually appear in the source."""
    used = set()
    for name in names:
        # Simple token check — not perfect but safe (won't false-positive)
        if name in source:
            used.add(name)
    return used


def scan_file(path: Path) -> list:
    """Return list of suspected dead-code items in a single file."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [{"type": "parse_error", "file": str(path), "detail": str(e)}]

    defined = collect_defined_names(tree)
    issues = []

    # Check for unused imports
    for imp in defined["imports"]:
        # Count occurrences beyond the import line itself
        uses = source.count(imp)
        if uses <= 1:
            issues.append({
                "type": "unused_import",
                "file": str(path.relative_to(REPO_ROOT)),
                "name": imp,
                "confidence": "high",
            })

    return issues


def scan_repo() -> list:
    """Scan all Python files in the repo for dead code."""
    all_issues = []
    py_files = [p for p in REPO_ROOT.rglob("*.py") if ".git" not in p.parts]
    for path in py_files:
        all_issues.extend(scan_file(path))
    return all_issues


# ── Approval Workflow ──────────────────────────────────────────────────────────

def save_pending(issues: list):
    STAGING_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "status": "pending_approval",
        "issues": issues,
    }
    STAGING_PATH.write_text(json.dumps(payload, indent=2))
    print(f"\n📋 Staged to: {STAGING_PATH.relative_to(REPO_ROOT)}")


def present_issues(issues: list):
    if not issues:
        print("✅ No dead code detected.")
        return

    print(f"\n{'='*60}")
    print(f"GH05T3 SELF-IMPROVEMENT REPORT — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"{'='*60}")
    print(f"Found {len(issues)} issue(s) requiring your approval:\n")

    for i, issue in enumerate(issues, 1):
        print(f"  [{i}] {issue['type'].upper()}")
        print(f"      File: {issue['file']}")
        if "name" in issue:
            print(f"      Name: {issue['name']}")
        if "confidence" in issue:
            print(f"      Confidence: {issue['confidence']}")
        print()

    print("─" * 60)
    print("NOTHING HAS BEEN CHANGED.")
    print("To approve all:   python tools/self_improve.py --apply")
    print("To reject all:    python tools/self_improve.py --reject")
    print("─" * 60)


def apply_approved():
    if not STAGING_PATH.exists():
        print("No pending cleanup found. Run without --apply first.")
        sys.exit(1)

    payload = json.loads(STAGING_PATH.read_text())
    if payload["status"] != "pending_approval":
        print(f"Status is '{payload['status']}' — nothing to apply.")
        sys.exit(0)

    issues = payload["issues"]
    applied = []

    for issue in issues:
        if issue["type"] == "unused_import":
            path = REPO_ROOT / issue["file"]
            if not path.exists():
                continue
            source = path.read_text(encoding="utf-8")
            lines = source.splitlines(keepends=True)
            new_lines = [
                line for line in lines
                if not (issue["name"] in line and (
                    line.strip().startswith("import ") or
                    line.strip().startswith("from ")
                ))
            ]
            if new_lines != lines:
                path.write_text("".join(new_lines), encoding="utf-8")
                applied.append(issue)
                print(f"  ✂️  Removed unused import '{issue['name']}' from {issue['file']}")

    # Log what was done
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": "apply_cleanup",
        "applied_count": len(applied),
        "items": applied,
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

    # Clear staging
    payload["status"] = "applied"
    STAGING_PATH.write_text(json.dumps(payload, indent=2))
    print(f"\n✅ Applied {len(applied)} change(s). Logged to {LOG_PATH.relative_to(REPO_ROOT)}")


def reject_pending():
    if not STAGING_PATH.exists():
        print("No pending cleanup found.")
        sys.exit(0)
    payload = json.loads(STAGING_PATH.read_text())
    payload["status"] = "rejected"
    STAGING_PATH.write_text(json.dumps(payload, indent=2))

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": "reject_cleanup",
        "issue_count": len(payload["issues"]),
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

    print("❌ Cleanup rejected. No files changed.")


# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--apply" in sys.argv:
        apply_approved()
    elif "--reject" in sys.argv:
        reject_pending()
    else:
        print("🔍 Scanning repo for dead code...")
        issues = scan_repo()
        save_pending(issues)
        present_issues(issues)
