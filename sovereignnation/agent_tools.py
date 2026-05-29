"""
agent_tools.py — OpenClaw-style tool loop for CODEX (and optionally other agents).

Implements the Pi runtime pattern from OpenClaw:
  4 core tools: read_file, write_file, bash_exec, list_directory
  + search_files, http_get for extended capability

CODEX runs in an agentic loop — calls tools repeatedly until the task is done
or max_turns is reached. This is what separates it from a single-shot LLM call.

Safety:
  - Dangerous command patterns are blocked
  - Subprocess timeout at 30s per command
  - File reads capped at 8KB
  - All actions logged

Ollama tool-call format is used (compatible with qwen2.5:7b, llama3.1, etc.)
"""

import subprocess
import json
import logging
import time
from pathlib import Path

import httpx

log = logging.getLogger("agent_tools")

OLLAMA_URL = "http://localhost:11434"

# Default working directory for bash_exec — project root
WORK_DIR = str(Path(__file__).parent.parent.parent)

# Patterns that will never be executed
DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    "format c:",
    "del /s /q c:\\",
    "del /f /s /q",
    "shutdown /",
    "reboot",
    ":(){:|:&};:",     # fork bomb
    "dd if=/dev/zero",
    "mkfs",
    "fdisk",
    "diskpart",
    "reg delete",
    "rd /s /q c:",
]

# ─── Tool Definitions (Ollama format) ────────────────────────────────────────

CODEX_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash_exec",
            "description": (
                "Execute a shell command and return stdout + stderr. "
                "Use for: running Python scripts, pip install, git commands, "
                "checking process status, creating directories, running tests."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to run"
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory (optional)"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the text contents of a file. Returns up to 8000 characters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative file path"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Character offset to start reading from (optional)"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or append content to a file. Creates parent directories if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "mode": {
                        "type": "string",
                        "enum": ["overwrite", "append"],
                        "description": "overwrite (default) or append"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and subdirectories in a path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern e.g. *.py (default: *)"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for text patterns across files in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search"},
                    "pattern": {"type": "string", "description": "Text or regex to search for"},
                    "file_glob": {
                        "type": "string",
                        "description": "File filter e.g. *.py (optional)"
                    }
                },
                "required": ["path", "pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "Make an HTTP GET request to a local service or API and return the response.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 10)"}
                },
                "required": ["url"]
            }
        }
    },
]

# Subset of tools for ORACLE and FORGE (read-only, no write/exec)
ANALYST_TOOLS = [t for t in CODEX_TOOLS if t["function"]["name"] in ("read_file", "list_directory", "search_files", "http_get")]


# ─── Tool Executor ────────────────────────────────────────────────────────────

def _is_dangerous(command: str) -> bool:
    cmd_lower = command.lower().strip()
    return any(p.lower() in cmd_lower for p in DANGEROUS_PATTERNS)


def execute_tool(tool_name: str, params: dict) -> str:
    """Execute a single tool call and return result as string."""
    try:
        if tool_name == "bash_exec":
            command = params.get("command", "").strip()
            if not command:
                return "ERROR: empty command"
            if _is_dangerous(command):
                return f"BLOCKED: Dangerous command pattern detected. Command not executed."
            cwd = params.get("cwd", WORK_DIR)
            log.info(f"bash_exec: {command[:80]}")
            result = subprocess.run(
                command, shell=True, capture_output=True,
                text=True, cwd=cwd, timeout=30
            )
            output = (result.stdout + result.stderr).strip()
            if not output:
                return f"(exit code {result.returncode}, no output)"
            return output[:4000]

        elif tool_name == "read_file":
            path = Path(params["path"])
            if not path.exists():
                return f"ERROR: File not found: {params['path']}"
            if not path.is_file():
                return f"ERROR: Not a file: {params['path']}"
            offset = params.get("offset", 0)
            content = path.read_text(encoding="utf-8", errors="replace")
            if offset:
                content = content[offset:]
            return content[:8000]

        elif tool_name == "write_file":
            path = Path(params["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if params.get("mode") == "append" else "w"
            content = params["content"]
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)
            return f"OK: {'appended' if mode == 'a' else 'wrote'} {len(content)} chars to {path}"

        elif tool_name == "list_directory":
            p = Path(params["path"])
            if not p.exists():
                return f"ERROR: Path not found: {params['path']}"
            pattern = params.get("pattern", "*")
            entries = sorted(p.glob(pattern))
            lines = []
            for e in entries[:100]:
                tag = "[DIR] " if e.is_dir() else "[FILE]"
                size = "" if e.is_dir() else f" ({e.stat().st_size:,} bytes)"
                lines.append(f"{tag} {e.name}{size}")
            return "\n".join(lines) if lines else "(empty directory)"

        elif tool_name == "search_files":
            path = params["path"]
            pattern = params["pattern"]
            file_glob = params.get("file_glob", "")
            cmd = f'grep -rn "{pattern}" "{path}"'
            if file_glob:
                cmd += f' --include="{file_glob}"'
            result = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, timeout=15
            )
            output = (result.stdout + result.stderr).strip()
            return output[:4000] if output else "(no matches found)"

        elif tool_name == "http_get":
            import httpx as _httpx
            url = params["url"]
            timeout = params.get("timeout", 10)
            resp = _httpx.get(url, timeout=timeout)
            text = resp.text[:3000]
            return f"HTTP {resp.status_code}\n{text}"

        else:
            return f"ERROR: Unknown tool '{tool_name}'"

    except subprocess.TimeoutExpired:
        return "ERROR: Command timed out (30s limit)"
    except PermissionError as e:
        return f"ERROR: Permission denied — {e}"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


# ─── Agentic Loop ─────────────────────────────────────────────────────────────

async def run_agent_loop(
    messages: list,
    system: str,
    model: str = "qwen2.5:7b",
    tools: list = None,
    max_turns: int = 10,
    max_tokens: int = 1500,
    temperature: float = 0.4,
) -> dict:
    """
    Run an agentic tool loop (OpenClaw Pi runtime pattern).

    Calls Ollama repeatedly:
      1. Model responds with text or tool_calls
      2. If tool_calls → execute → append results → repeat
      3. If no tool_calls → task complete, return final response

    Args:
        messages:   conversation history (user/assistant messages)
        system:     system prompt (with skills injected)
        model:      Ollama model name
        tools:      list of tool definitions (defaults to CODEX_TOOLS)
        max_turns:  safety ceiling on loop iterations
        max_tokens: max tokens per model call
        temperature: 0.4 is good for tool-use tasks (lower = more precise)

    Returns:
        dict with message, tool_log, turns_used, elapsed_seconds
    """
    if tools is None:
        tools = CODEX_TOOLS

    ollama_messages = []
    if system:
        ollama_messages.append({"role": "system", "content": system})
    ollama_messages.extend(messages)

    t0 = time.time()
    tool_log = []

    async with httpx.AsyncClient(timeout=120) as client:
        for turn in range(max_turns):
            payload = {
                "model": model,
                "messages": ollama_messages,
                "stream": False,
                "tools": tools,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            }

            r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            if r.status_code != 200:
                return {
                    "error": f"Ollama returned {r.status_code}: {r.text[:200]}",
                    "turns_used": turn,
                }

            data = r.json()
            msg = data.get("message", {})
            tool_calls = msg.get("tool_calls") or []

            if not tool_calls:
                # No more tool calls — task complete
                elapsed = round(time.time() - t0, 2)
                eval_count = data.get("eval_count", 0)
                eval_dur   = data.get("eval_duration", 1)
                tps = round(eval_count / (eval_dur / 1e9), 1) if eval_dur else 0

                return {
                    "message":         {"content": msg.get("content", "")},
                    "tool_log":        tool_log,
                    "turns_used":      turn + 1,
                    "elapsed_seconds": elapsed,
                    "tok_per_sec":     tps,
                    "routed_to":       "codex",
                }

            # ── Execute tool calls ──────────────────────────────────────────
            # Append assistant's tool-call message
            assistant_msg = {
                "role": "assistant",
                "content": msg.get("content") or "",
                "tool_calls": tool_calls,
            }
            ollama_messages.append(assistant_msg)

            for tc in tool_calls:
                fn        = tc.get("function", {})
                tool_name = fn.get("name", "unknown")
                # Ollama may pass arguments as a string or dict
                raw_args  = fn.get("arguments", {})
                tool_params = raw_args if isinstance(raw_args, dict) else {}
                if isinstance(raw_args, str):
                    try:
                        tool_params = json.loads(raw_args)
                    except Exception:
                        tool_params = {}

                log.info(f"Tool call [{turn+1}/{max_turns}]: {tool_name}({list(tool_params.keys())})")
                result = execute_tool(tool_name, tool_params)

                tool_log.append({
                    "turn":    turn + 1,
                    "tool":    tool_name,
                    "params":  {k: str(v)[:80] for k, v in tool_params.items()},
                    "result":  result[:200],
                })

                # Append tool result message
                ollama_messages.append({
                    "role":    "tool",
                    "content": result,
                })

    # Max turns exhausted
    return {
        "message":         {"content": "(agent reached max_turns without completing — try a more specific task)"},
        "tool_log":        tool_log,
        "turns_used":      max_turns,
        "elapsed_seconds": round(time.time() - t0, 2),
        "warning":         "max_turns_reached",
        "routed_to":       "codex",
    }
