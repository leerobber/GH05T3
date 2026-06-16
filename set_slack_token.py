"""
set_slack_token.py — manually save a Slack bot token to backend/.env

Bypasses the OAuth popup entirely. Use this when:
  - The OAuth callback port is blocked (Docker, Node, etc.)
  - You already have a valid xoxb- token from api.slack.com

Usage:
  python set_slack_token.py xoxb-YOUR-TOKEN-HERE

Get your token:
  1. Go to https://api.slack.com/apps
  2. Click your app -> OAuth & Permissions
  3. Click 'Reinstall to Workspace' (or 'Install to Workspace')
  4. Copy the Bot User OAuth Token (starts with xoxb-)
"""
import os, sys, requests
from pathlib import Path

BACKEND_ENV = Path(__file__).parent / "backend" / ".env"
ROOT_ENV    = Path(__file__).parent / ".env"


def _test_token(token: str) -> dict:
    try:
        r = requests.post(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _update_env(path: Path, key: str, value: str):
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{key}={value}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"  Saved {key} to {path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    token = sys.argv[1].strip()

    if not token.startswith("xoxb-"):
        print(f"ERROR: Expected a bot token starting with 'xoxb-', got: {token[:20]}...")
        print("Get it from: api.slack.com/apps -> your app -> OAuth & Permissions")
        sys.exit(1)

    print(f"\nTesting token {token[:20]}...")
    result = _test_token(token)

    if not result.get("ok"):
        print(f"  WARNING: Slack returned error: {result.get('error')}")
        print("  The token may be invalid or have insufficient scopes.")
        ans = input("  Save it anyway? [y/N]: ").strip().lower()
        if ans != "y":
            sys.exit(1)
    else:
        team = result.get("team", "?")
        bot  = result.get("user", "?")
        print(f"  Token valid  workspace={team}  bot={bot}")

    # Save to both env files so cmd_listener finds it regardless of load order
    _update_env(BACKEND_ENV, "SLACK_BOT_TOKEN", token)
    _update_env(ROOT_ENV, "SLACK_BOT_TOKEN", token)

    print("\nDone. Restart cmd_listener.py to connect.")
