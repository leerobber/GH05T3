"""
ghost_chat.py — Streaming CLI agent for GH05T3
Replaces Hermes: direct Ollama streaming, PowerShell-native, no framework overhead.

Speed wins over Hermes:
  - Tokens stream to terminal as they arrive (Hermes waits for full response)
  - No provider abstraction layer / auth resolution
  - No ghost session replay
  - PowerShell shell tool (bash_exec was broken on Windows in Hermes)

Usage:
    python ghost_chat.py
    python ghost_chat.py --model qwen2.5:7b
    python ghost_chat.py --no-tools   (text-only, fastest)
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_URL  = "http://localhost:11434"
SOUL_PATH   = Path(r"C:\Users\leer4\AppData\Local\hermes\SOUL.md")
HISTORY_DIR = Path(r"C:\Users\leer4\AppData\Local\hermes\ghost_sessions")
WORK_DIR    = Path(r"C:\Users\leer4\GH05T3")

# ANSI (Windows Terminal supports these)
R   = "\033[0m"
B   = "\033[1m"
C   = "\033[36m"
Y   = "\033[33m"
G   = "\033[32m"
M   = "\033[35m"
DIM = "\033[2m"

# ── System prompt ─────────────────────────────────────────────────────────────
def load_soul() -> str:
    if SOUL_PATH.exists():
        return SOUL_PATH.read_text(encoding="utf-8")
    return "You are a helpful AI coding assistant. Be direct and concise."

# ── Tools ─────────────────────────────────────────────────────────────────────
DANGEROUS = [
    "rm -rf /", "rm -rf ~", "format c:", "del /s /q c:\\",
    "shutdown /", "reboot", ":(){:|:&};:", "dd if=/dev/zero",
    "mkfs", "diskpart", "reg delete", "rd /s /q c:",
]

def _is_dangerous(cmd: str) -> bool:
    lo = cmd.lower()
    return any(p.lower() in lo for p in DANGEROUS)

def execute_tool(name: str, params: dict) -> str:
    try:
        if name == "bash_exec":
            command = params.get("command", "").strip()
            if not command:
                return "ERROR: empty command"
            if _is_dangerous(command):
                return "BLOCKED: dangerous command pattern"
            cwd = params.get("cwd", str(WORK_DIR))
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, text=True, cwd=cwd, timeout=30,
            )
            out = (result.stdout + result.stderr).strip()
            return out[:4000] if out else f"(exit {result.returncode}, no output)"

        elif name == "read_file":
            p = Path(params["path"])
            if not p.exists():
                return f"ERROR: not found: {params['path']}"
            if not p.is_file():
                return f"ERROR: not a file: {params['path']}"
            offset = params.get("offset", 0)
            content = p.read_text(encoding="utf-8", errors="replace")
            return content[offset:][:8000]

        elif name == "write_file":
            p = Path(params["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if params.get("mode") == "append" else "w"
            with open(p, mode, encoding="utf-8") as f:
                f.write(params["content"])
            return f"OK: wrote {len(params['content'])} chars to {p}"

        elif name == "list_directory":
            p = Path(params["path"])
            if not p.exists():
                return f"ERROR: not found: {params['path']}"
            pattern = params.get("pattern", "*")
            entries = sorted(p.glob(pattern))
            lines = []
            for e in entries[:100]:
                tag = "[DIR] " if e.is_dir() else "[FILE]"
                sz = "" if e.is_dir() else f" ({e.stat().st_size:,}b)"
                lines.append(f"{tag} {e.name}{sz}")
            return "\n".join(lines) if lines else "(empty)"

        elif name == "search_files":
            path = params["path"]
            pattern = params["pattern"]
            file_glob = params.get("file_glob", "*.py")
            cmd = (
                f'Select-String -Path "{path}\\{file_glob}" '
                f'-Pattern "{pattern}" -Recurse -ErrorAction SilentlyContinue '
                f'| Select-Object -First 50 | ForEach-Object {{ $_.ToString() }}'
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                capture_output=True, text=True, timeout=15,
            )
            out = result.stdout.strip()
            return out[:4000] if out else "(no matches)"

        elif name == "http_get":
            url = params["url"]
            timeout = params.get("timeout", 10)
            r = httpx.get(url, timeout=timeout)
            return f"HTTP {r.status_code}\n{r.text[:3000]}"

        else:
            return f"ERROR: unknown tool '{name}'"

    except subprocess.TimeoutExpired:
        return "ERROR: timed out (30s)"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


TOOLS = [
    {"type": "function", "function": {
        "name": "bash_exec",
        "description": "Run a PowerShell command. Returns stdout + stderr. Use for git, python, file ops, process checks.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "PowerShell command to run"},
            "cwd": {"type": "string", "description": "Working directory (default: GH05T3 root)"},
        }, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read file contents. Returns up to 8000 chars.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "offset": {"type": "integer", "description": "Char offset to start from"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write or append to a file. Creates parent dirs if needed.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "mode": {"type": "string", "enum": ["overwrite", "append"]},
        }, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "list_directory",
        "description": "List files and subdirectories.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "pattern": {"type": "string", "description": "Glob filter e.g. *.py"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "search_files",
        "description": "Search for a pattern across files in a directory.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "pattern": {"type": "string"},
            "file_glob": {"type": "string", "description": "File filter e.g. *.py (default: *.py)"},
        }, "required": ["path", "pattern"]},
    }},
    {"type": "function", "function": {
        "name": "http_get",
        "description": "HTTP GET to a local service (Ollama, pipeline_backend, NPU, etc).",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string"},
            "timeout": {"type": "integer"},
        }, "required": ["url"]},
    }},
]

# ── Text-based tool call fallback ─────────────────────────────────────────────
# For models that don't support native Ollama tool_calls (e.g. qwen2.5-coder:7b)
# — they output the JSON as plain text instead. This parser extracts and executes it.

_TOOL_NAMES = {"bash_exec", "read_file", "write_file", "list_directory", "search_files", "http_get"}

def _extract_text_tool_calls(content: str) -> list:
    """Pull tool call JSON objects out of plain-text model output."""
    calls = []
    i = 0
    while i < len(content):
        idx = content.find('{', i)
        if idx == -1:
            break
        # Walk to matching closing brace
        depth, end = 0, idx
        for j, ch in enumerate(content[idx:], idx):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = j
                    break
        try:
            obj = json.loads(content[idx:end + 1])
            name = obj.get("name") or obj.get("tool")
            params = (
                obj.get("parameters")
                or obj.get("arguments")
                or obj.get("params")
                or {}
            )
            if name in _TOOL_NAMES and isinstance(params, dict):
                calls.append({"function": {"name": name, "arguments": params}})
        except (json.JSONDecodeError, Exception):
            pass
        i = end + 1
    return calls


# ── Streaming response ─────────────────────────────────────────────────────────

async def stream_turn(messages: list, model: str, system: str, use_tools: bool) -> dict:
    """
    Stream one model turn. Prints tokens live.
    Returns {"content": str, "tool_calls": list, "elapsed": float}
    """
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream": True,
        "options": {"temperature": 0.4, "num_predict": 2048},
    }
    if use_tools:
        payload["tools"] = TOOLS

    full_content = ""
    tool_calls = []
    t0 = time.time()

    print(f"\n{C}{B}Ghost{R}  ", end="", flush=True)

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    print(f"\n{Y}[Ollama error {resp.status_code}: {body[:200].decode()}]{R}")
                    return {"content": "", "tool_calls": [], "elapsed": 0}

                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg = chunk.get("message", {})
                    delta = msg.get("content", "")
                    if delta:
                        print(delta, end="", flush=True)
                        full_content += delta

                    tcs = msg.get("tool_calls")
                    if tcs:
                        tool_calls = tcs

    except httpx.ConnectError:
        print(f"\n{Y}[Cannot connect to Ollama — is it running?]{R}")
    except httpx.ReadTimeout:
        print(f"\n{Y}[Timeout — model may be loading, try again]{R}")

    print()  # newline
    elapsed = round(time.time() - t0, 2)

    # Fallback: model printed tool call JSON as text instead of using tool_calls field
    if use_tools and not tool_calls and full_content.strip():
        parsed = _extract_text_tool_calls(full_content)
        if parsed:
            tool_calls = parsed
            full_content = ""  # suppress the raw JSON from being treated as prose

    return {"content": full_content, "tool_calls": tool_calls, "elapsed": elapsed}


async def agent_loop(user_input: str, history: list, model: str, system: str, use_tools: bool) -> list:
    """
    Full agentic turn: stream → execute tools → stream again until no tools called.
    """
    history.append({"role": "user", "content": user_input})
    messages = history.copy()

    for turn in range(8):
        result = await stream_turn(messages, model, system, use_tools)

        content = result["content"]
        tool_calls = result["tool_calls"]

        if not tool_calls:
            history.append({"role": "assistant", "content": content})
            elapsed = result["elapsed"]
            if elapsed > 0:
                print(f"{DIM}  ({elapsed}s){R}")
            break

        # Model wants to call tools — append its message, execute, feed results back
        messages.append({
            "role": "assistant",
            "content": content or "",
            "tool_calls": tool_calls,
        })

        for tc in tool_calls:
            fn = tc.get("function", {})
            tool_name = fn.get("name", "unknown")
            raw_args = fn.get("arguments", {})
            params = raw_args if isinstance(raw_args, dict) else {}
            if isinstance(raw_args, str):
                try:
                    params = json.loads(raw_args)
                except Exception:
                    params = {}

            short_params = ", ".join(f"{k}={str(v)[:50]}" for k, v in params.items())
            print(f"{DIM}  ▸ {tool_name}({short_params}){R}", flush=True)

            tool_result = execute_tool(tool_name, params)
            preview = tool_result[:100].replace("\n", " ")
            print(f"{DIM}    → {preview}{R}", flush=True)

            messages.append({"role": "tool", "content": tool_result})

    return history

# ── Session history ────────────────────────────────────────────────────────────

def save_history(history: list, session_id: str):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = HISTORY_DIR / f"{session_id}.json"
    path.write_text(json.dumps(history, indent=2), encoding="utf-8")

def load_last_history() -> tuple:
    if not HISTORY_DIR.exists():
        return [], None
    sessions = sorted(HISTORY_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not sessions:
        return [], None
    p = sessions[0]
    try:
        return json.loads(p.read_text(encoding="utf-8")), p.stem
    except Exception:
        return [], None

# ── CLI ────────────────────────────────────────────────────────────────────────

COMMANDS = {
    "/exit":     "Save and exit",
    "/clear":    "Clear conversation history",
    "/model X":  "Switch model mid-session",
    "/tools":    "List available tools",
    "/notool":   "Toggle tool use on/off",
    "/last":     "Resume last session",
    "/save":     "Force save current session",
    "/help":     "Show this list",
}

def print_banner(model: str, use_tools: bool):
    tool_str = "file · shell · search · http" if use_tools else "text only"
    print(f"\n{B}{C}  GHOST CHAT{R}  {DIM}streaming · PowerShell-native · zero overhead{R}")
    print(f"  model: {G}{model}{R}  ·  {tool_str}")
    print(f"  {DIM}/help for commands  ·  Ctrl+C to exit{R}\n")


async def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--no-tools", action="store_true")
    args = parser.parse_args()

    # Enable ANSI on Windows
    os.system("")

    model     = args.model
    use_tools = not args.no_tools
    system    = load_soul()
    history   = []
    session_id = str(int(time.time()))

    print_banner(model, use_tools)

    try:
        while True:
            try:
                user_input = input(f"{M}you{R}  ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                cmd = user_input.split()[0].lower()
                rest = user_input[len(cmd):].strip()

                if cmd in ("/exit", "/quit"):
                    print(f"{DIM}saving...{R}")
                    save_history(history, session_id)
                    break

                elif cmd == "/clear":
                    history = []
                    print(f"{DIM}history cleared{R}")

                elif cmd == "/model":
                    if rest:
                        model = rest
                        print(f"{DIM}model → {model}{R}")
                    else:
                        print(f"current model: {model}")

                elif cmd == "/tools":
                    for t in TOOLS:
                        f = t["function"]
                        print(f"  {G}{f['name']}{R}: {f['description'][:70]}")

                elif cmd == "/notool":
                    use_tools = not use_tools
                    print(f"{DIM}tools {'enabled' if use_tools else 'disabled'}{R}")

                elif cmd == "/last":
                    h, sid = load_last_history()
                    if h:
                        history = h
                        print(f"{DIM}loaded {len(h)} messages from {sid}{R}")
                    else:
                        print(f"{DIM}no saved sessions{R}")

                elif cmd == "/save":
                    save_history(history, session_id)
                    print(f"{DIM}saved → {session_id}.json{R}")

                elif cmd == "/help":
                    for c, d in COMMANDS.items():
                        print(f"  {G}{c}{R}: {d}")

                continue

            history = await agent_loop(user_input, history, model, system, use_tools)
            save_history(history, session_id)

    except KeyboardInterrupt:
        print(f"\n{DIM}saving...{R}")
        if history:
            save_history(history, session_id)

    print(f"{DIM}bye{R}\n")


if __name__ == "__main__":
    asyncio.run(main())
