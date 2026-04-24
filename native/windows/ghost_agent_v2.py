#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║          GH05T3  ·  SOVEREIGN COMPANION AGENT  v2.0             ║
║          Local execution node for the Sovereign Core mesh       ║
╠══════════════════════════════════════════════════════════════════╣
║  Enhancements over v1:                                          ║
║  • ReAct reasoning loop — plan → act → observe → reflect       ║
║  • Local LLM routing  — hits port 8000 gateway (TatorTot mesh) ║
║  • SQLite memory      — persistent cross-session recall         ║
║  • Mic → STT pipeline — vosk offline transcription             ║
║  • Process manager    — launch / monitor / kill local procs     ║
║  • Sys health beacon  — CPU/RAM/GPU pushed every N seconds      ║
║  • Secure token vault — encrypted credential store (Fernet)    ║
║  • Structured audit   — JSONL tamper-evident action log        ║
║  • Reconnect with JTI — jitter+backoff, session continuity     ║
║  • Kill switch        — Ctrl+Shift+K global hotkey             ║
╚══════════════════════════════════════════════════════════════════╝

Install:
    pip install websockets psutil cryptography pillow mss pyperclip \
                vosk sounddevice rich aiohttp aiosqlite

Run:
    python ghost_agent_v2.py [--all] [--llm-port 8000] [--react]

Headless:
    GHOST_GATEWAY_URL=https://your-gh05t3.app PAIR_CODE=123456 \\
    python ghost_agent_v2.py --all --react
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import hmac
import io
import json
import logging
import os
import platform
import queue
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

# ── Optional heavy imports (graceful degradation) ────────────────────────────
try:
    import websockets
except ImportError:
    print("pip install websockets")
    sys.exit(1)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    import aiosqlite
    HAS_AIOSQLITE = True
except ImportError:
    HAS_AIOSQLITE = False

try:
    from rich.console import Console
    from rich.logging import RichHandler
    HAS_RICH = True
    _console = Console()
except ImportError:
    HAS_RICH = False

# ── Logging ───────────────────────────────────────────────────────────────────
_handlers = [logging.FileHandler("ghost_agent.log")]
if HAS_RICH:
    _handlers.append(RichHandler(console=_console, rich_tracebacks=True, show_path=False))
else:
    _handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="[%H:%M:%S]",
    handlers=_handlers,
)
LOG = logging.getLogger("GH05T3")

# ── Audit log (JSONL, tamper-evident via HMAC chain) ─────────────────────────
AUDIT_LOG = Path("ghost_audit.jsonl")
_AUDIT_SECRET = os.environ.get("GHOST_AUDIT_SECRET", "gh05t3-default-secret").encode()
_last_audit_hash = "GENESIS"

def _audit(action: str, actor: str, outcome: str, detail: dict | None = None):
    global _last_audit_hash
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": _SESSION_ID,
        "action": action,
        "actor": actor,
        "outcome": outcome,
        "detail": detail or {},
        "prev_hash": _last_audit_hash,
    }
    payload = json.dumps(entry, separators=(",", ":")).encode()
    sig = hmac.new(_AUDIT_SECRET, payload, hashlib.sha256).hexdigest()
    entry["sig"] = sig
    _last_audit_hash = sig
    with AUDIT_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")

_SESSION_ID = str(uuid.uuid4())[:8]

# ── Shell allowlist ───────────────────────────────────────────────────────────
SHELL_ALLOWLIST = {
    "git", "ls", "dir", "pwd", "cat", "type", "echo", "python", "python3",
    "pytest", "node", "yarn", "npm", "pip", "pip3", "make", "cmake",
    "gcc", "clang", "rustc", "cargo", "go", "docker", "kubectl",
    "tree", "grep", "rg", "fd", "find", "curl", "wget",
    "whoami", "hostname", "uname", "date", "which", "where",
    "head", "tail", "wc", "du", "df", "ps", "top", "free", "uptime",
    "nvtop", "nvidia-smi", "rocm-smi",           # GPU monitoring
    "vllm", "llama-server", "ollama",             # inference
    "systemctl", "journalctl",                    # service management (Linux)
    "tasklist", "taskkill",                       # Windows process management
}

# ── Dataclasses ───────────────────────────────────────────────────────────────
@dataclass
class ReActStep:
    thought: str
    action: str
    observation: str
    reflection: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class AgentConfig:
    gateway: str
    token: str
    label: str
    caps: set[str]
    fs_read_roots: list[Path]
    fs_write_roots: list[Path]
    allow_any_shell: bool
    ghosteye: bool
    ghosteye_interval: int
    ghosteye_ocr: bool
    llm_port: int
    react_enabled: bool
    health_interval: int
    vault_key: bytes | None


# ═══════════════════════════════════════════════════════════════════
# MEMORY — SQLite-backed persistent recall
# ═══════════════════════════════════════════════════════════════════
class GhostMemory:
    """Lightweight persistent memory using aiosqlite or sync sqlite3."""

    def __init__(self, db_path: str = "ghost_memory.db"):
        self.db_path = db_path
        self._init_sync()

    def _init_sync(self):
        con = sqlite3.connect(self.db_path)
        con.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                session TEXT,
                key     TEXT NOT NULL,
                value   TEXT NOT NULL,
                tags    TEXT DEFAULT '',
                ts      TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_key ON memories(key);
            CREATE TABLE IF NOT EXISTS react_history (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                session   TEXT,
                goal      TEXT,
                steps     TEXT,
                outcome   TEXT,
                ts        TEXT NOT NULL
            );
        """)
        con.commit()
        con.close()
        LOG.info("Memory DB ready: %s", self.db_path)

    def remember(self, key: str, value: Any, tags: str = ""):
        con = sqlite3.connect(self.db_path)
        con.execute(
            "INSERT INTO memories(session,key,value,tags,ts) VALUES(?,?,?,?,?)",
            (_SESSION_ID, key, json.dumps(value), tags,
             datetime.now(timezone.utc).isoformat())
        )
        con.commit()
        con.close()

    def recall(self, key: str, limit: int = 5) -> list[dict]:
        con = sqlite3.connect(self.db_path)
        rows = con.execute(
            "SELECT value, ts FROM memories WHERE key=? ORDER BY id DESC LIMIT ?",
            (key, limit)
        ).fetchall()
        con.close()
        return [{"value": json.loads(r[0]), "ts": r[1]} for r in rows]

    def recall_recent(self, limit: int = 20) -> list[dict]:
        con = sqlite3.connect(self.db_path)
        rows = con.execute(
            "SELECT key, value, ts FROM memories ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        con.close()
        return [{"key": r[0], "value": json.loads(r[1]), "ts": r[2]} for r in rows]

    def save_react_run(self, goal: str, steps: list[ReActStep], outcome: str):
        con = sqlite3.connect(self.db_path)
        con.execute(
            "INSERT INTO react_history(session,goal,steps,outcome,ts) VALUES(?,?,?,?,?)",
            (_SESSION_ID, goal,
             json.dumps([asdict(s) for s in steps]),
             outcome,
             datetime.now(timezone.utc).isoformat())
        )
        con.commit()
        con.close()

MEMORY = GhostMemory()


# ═══════════════════════════════════════════════════════════════════
# SECURE VAULT — encrypted credential/secret storage
# ═══════════════════════════════════════════════════════════════════
class GhostVault:
    def __init__(self, key: bytes | None = None):
        if not HAS_CRYPTO:
            LOG.warning("cryptography not installed — vault disabled")
            self._fernet = None
            return
        if key is None:
            key = Fernet.generate_key()
            LOG.info("Generated new vault key. Set GHOST_VAULT_KEY env var to persist.")
        self._fernet = Fernet(key)
        self._store: dict[str, bytes] = {}

    def put(self, name: str, secret: str) -> dict:
        if not self._fernet:
            return {"error": "vault unavailable (pip install cryptography)"}
        self._store[name] = self._fernet.encrypt(secret.encode())
        return {"stored": name}

    def get(self, name: str) -> dict:
        if not self._fernet:
            return {"error": "vault unavailable"}
        if name not in self._store:
            return {"error": f"no secret named '{name}'"}
        return {"name": name, "value": self._fernet.decrypt(self._store[name]).decode()}

    def list_keys(self) -> dict:
        return {"keys": list(self._store.keys())}


# ═══════════════════════════════════════════════════════════════════
# SYSTEM HEALTH BEACON
# ═══════════════════════════════════════════════════════════════════
def _collect_health() -> dict:
    h: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "os": platform.system(),
    }
    if HAS_PSUTIL:
        h["cpu_pct"] = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        h["ram_used_gb"] = round(mem.used / 1e9, 2)
        h["ram_total_gb"] = round(mem.total / 1e9, 2)
        h["ram_pct"] = mem.percent
        try:
            disk = psutil.disk_usage("/")
            h["disk_free_gb"] = round(disk.free / 1e9, 2)
        except Exception:
            pass
    # GPU — nvidia-smi
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            gpus = []
            for line in out.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) == 5:
                    gpus.append({
                        "name": parts[0], "util_pct": parts[1],
                        "mem_used_mb": parts[2], "mem_total_mb": parts[3], "temp_c": parts[4]
                    })
            if gpus:
                h["gpus"] = gpus
        except Exception:
            pass
    # ROCm
    if shutil.which("rocm-smi"):
        try:
            out = subprocess.run(["rocm-smi", "--showuse", "--showmeminfo", "vram", "--json"],
                                 capture_output=True, text=True, timeout=5)
            h["rocm"] = json.loads(out.stdout)
        except Exception:
            pass
    return h


async def _health_beacon_loop(ws, interval: int):
    LOG.info("Health beacon started — interval=%ds", interval)
    while True:
        try:
            await asyncio.sleep(interval)
            health = _collect_health()
            await ws.send(json.dumps({"event": "health_beacon", "data": health}))
        except asyncio.CancelledError:
            break
        except Exception:
            LOG.exception("health beacon error")


# ═══════════════════════════════════════════════════════════════════
# LOCAL LLM BRIDGE — routes to TatorTot mesh (port 8000 gateway)
# ═══════════════════════════════════════════════════════════════════
async def call_local_llm(
    prompt: str,
    llm_port: int = 8000,
    system: str = "You are GH05T3, a precise local AI companion.",
    max_tokens: int = 512,
    model: str = "auto",
) -> str:
    """Hit the Sovereign Core FastAPI gateway. Falls back gracefully."""
    if not HAS_AIOHTTP:
        return "[LLM unavailable — pip install aiohttp]"
    url = f"http://localhost:{llm_port}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "stream": False,
    }
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status == 200:
                    data = await r.json()
                    return data["choices"][0]["message"]["content"]
                return f"[LLM error {r.status}]"
    except asyncio.TimeoutError:
        return "[LLM timeout]"
    except Exception as e:
        return f"[LLM unreachable: {e}]"


# ═══════════════════════════════════════════════════════════════════
# ReAct REASONING LOOP
# ═══════════════════════════════════════════════════════════════════
async def react_loop(
    goal: str,
    dispatch_fn,
    llm_port: int,
    max_steps: int = 6,
) -> dict:
    """
    Plan → Act → Observe → Reflect loop.
    Each iteration calls local LLM to decide the next action,
    executes it via _dispatch, feeds result back.
    """
    steps: list[ReActStep] = []
    context = f"GOAL: {goal}\n"
    recent_mem = MEMORY.recall_recent(10)
    if recent_mem:
        context += "RECENT MEMORY:\n" + json.dumps(recent_mem[-5:], indent=2) + "\n"

    REACT_SYSTEM = (
        "You are GH05T3's ReAct engine. For each step output EXACTLY:\n"
        "THOUGHT: <your reasoning>\n"
        "ACTION: <json: {\"action\": \"...\", \"args\": {...}} or {\"action\": \"done\", \"answer\": \"...\"}>\n"
        "Never deviate from this format. Available actions: shell, fs_read, fs_write, "
        "screenshot, clipboard_read, clipboard_write, notify, memory_recall, sys_health, done."
    )

    for step_num in range(max_steps):
        thought_prompt = (
            f"{context}\nStep {step_num + 1}/{max_steps}.\n"
            "Reason about what to do next. If goal is achieved use action=done."
        )
        raw = await call_local_llm(thought_prompt, llm_port=llm_port,
                                   system=REACT_SYSTEM, max_tokens=300)

        # Parse THOUGHT / ACTION
        thought, action_json = "", {}
        for line in raw.splitlines():
            if line.startswith("THOUGHT:"):
                thought = line[8:].strip()
            elif line.startswith("ACTION:"):
                try:
                    action_json = json.loads(line[7:].strip())
                except json.JSONDecodeError:
                    action_json = {"action": "done", "answer": "parse error"}

        if not action_json:
            action_json = {"action": "done", "answer": "no valid action produced"}

        action_name = action_json.get("action", "done")
        action_args = action_json.get("args", {})

        # Handle meta-actions
        if action_name == "done":
            step = ReActStep(
                thought=thought,
                action="done",
                observation=action_json.get("answer", "complete"),
                reflection="goal reached",
            )
            steps.append(step)
            break

        if action_name == "memory_recall":
            observation = str(MEMORY.recall(action_args.get("key", ""), limit=5))
        elif action_name == "sys_health":
            observation = json.dumps(_collect_health())
        else:
            observation = json.dumps(dispatch_fn(action_name, action_args))

        # Reflect
        reflect_prompt = (
            f"Observation from {action_name}: {observation[:800]}\n"
            "In one sentence: what did we learn and what is the next priority?"
        )
        reflection = await call_local_llm(reflect_prompt, llm_port=llm_port,
                                          system=REACT_SYSTEM, max_tokens=100)

        step = ReActStep(
            thought=thought,
            action=f"{action_name}({json.dumps(action_args)[:120]})",
            observation=observation[:500],
            reflection=reflection.strip(),
        )
        steps.append(step)
        context += (
            f"\nStep {step_num + 1}:\n"
            f"  THOUGHT: {thought}\n"
            f"  ACTION: {action_name}\n"
            f"  OBSERVATION: {observation[:300]}\n"
            f"  REFLECTION: {reflection.strip()}\n"
        )
        MEMORY.remember(f"react_step_{step_num}", asdict(step), tags="react")

    outcome = steps[-1].observation if steps else "no steps taken"
    MEMORY.save_react_run(goal, steps, outcome)
    _audit("react_loop", "agent", "complete", {"goal": goal, "steps": len(steps)})
    return {"steps": [asdict(s) for s in steps], "outcome": outcome}


# ═══════════════════════════════════════════════════════════════════
# PROCESS MANAGER
# ═══════════════════════════════════════════════════════════════════
_PROCESSES: dict[str, subprocess.Popen] = {}

def cap_proc_launch(name: str, cmd: str, caps: set[str]) -> dict:
    if "shell_exec" not in caps:
        return {"error": "shell_exec not granted"}
    if name in _PROCESSES and _PROCESSES[name].poll() is None:
        return {"error": f"process '{name}' already running"}
    try:
        tokens = shlex.split(cmd, posix=(os.name != "nt"))
        proc = subprocess.Popen(tokens, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True)
        _PROCESSES[name] = proc
        _audit("proc_launch", "remote", "ok", {"name": name, "cmd": cmd})
        return {"launched": name, "pid": proc.pid}
    except Exception as e:
        return {"error": str(e)}

def cap_proc_status() -> dict:
    statuses = {}
    for name, proc in _PROCESSES.items():
        rc = proc.poll()
        statuses[name] = {"pid": proc.pid, "running": rc is None, "returncode": rc}
    return {"processes": statuses}

def cap_proc_kill(name: str) -> dict:
    if name not in _PROCESSES:
        return {"error": f"no process named '{name}'"}
    proc = _PROCESSES[name]
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    _audit("proc_kill", "remote", "ok", {"name": name})
    return {"killed": name, "returncode": proc.returncode}


# ═══════════════════════════════════════════════════════════════════
# MICROPHONE CAPTURE → offline STT (vosk)
# ═══════════════════════════════════════════════════════════════════
def cap_mic_capture(duration_s: int = 5, model_path: str = "vosk-model") -> dict:
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError:
        return {"error": "pip install sounddevice numpy"}

    try:
        from vosk import Model, KaldiRecognizer
        if not Path(model_path).exists():
            return {"error": f"Vosk model not found at {model_path}. Download from alphacephei.com/vosk/models"}
        model = Model(model_path)
        rec = KaldiRecognizer(model, 16000)
    except ImportError:
        return {"error": "pip install vosk"}

    LOG.info("Capturing mic for %ds", duration_s)
    audio = sd.rec(int(duration_s * 16000), samplerate=16000,
                   channels=1, dtype="int16")
    sd.wait()
    audio_bytes = audio.tobytes()

    rec.AcceptWaveform(audio_bytes)
    result = json.loads(rec.FinalResult())
    text = result.get("text", "")
    _audit("mic_capture", "agent", "ok", {"duration_s": duration_s, "chars": len(text)})
    return {"transcript": text, "duration_s": duration_s}


# ═══════════════════════════════════════════════════════════════════
# CAPABILITY IMPLEMENTATIONS (enhanced)
# ═══════════════════════════════════════════════════════════════════
def cap_screenshot(monitor: int = 1, scale_width: int = 1280) -> dict:
    try:
        import mss
        from PIL import Image
    except ImportError:
        return {"error": "pip install mss pillow"}
    with mss.mss() as sct:
        monitors = sct.monitors
        mon_idx = min(monitor, len(monitors) - 1)
        img = sct.grab(monitors[mon_idx])
        pil = Image.frombytes("RGB", img.size, img.rgb)
        w, h = pil.size
        if w > scale_width:
            pil = pil.resize((scale_width, int(h * scale_width / w)))
        buf = io.BytesIO()
        pil.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        _audit("screenshot", "remote", "ok", {"monitor": mon_idx, "w": pil.size[0]})
        return {"png_b64": b64, "w": pil.size[0], "h": pil.size[1],
                "monitor": mon_idx, "total_monitors": len(monitors) - 1}


def cap_shell(cmd: str, allowlist: bool = True, timeout: int = 30,
              cwd: str | None = None) -> dict:
    if not cmd.strip():
        return {"error": "empty command"}
    tokens = shlex.split(cmd, posix=(os.name != "nt"))
    if allowlist:
        head = Path(tokens[0]).name.lower().removesuffix(".exe")
        if head not in SHELL_ALLOWLIST:
            return {"error": f"command '{head}' not in allow-list"}
    start = time.monotonic()
    try:
        proc = subprocess.run(
            tokens, capture_output=True, text=True, timeout=timeout,
            shell=False, cwd=cwd or None,
        )
        elapsed = round(time.monotonic() - start, 3)
        _audit("shell", "remote", "ok", {"cmd": cmd[:80], "rc": proc.returncode, "elapsed_s": elapsed})
        return {
            "stdout": proc.stdout[-12000:],
            "stderr": proc.stderr[-4000:],
            "rc": proc.returncode,
            "elapsed_s": elapsed,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout}s"}
    except FileNotFoundError:
        return {"error": f"not found: {tokens[0]}"}


def _path_in(roots: list[Path], target: Path) -> bool:
    try:
        t = target.resolve()
        return any(str(t).startswith(str(r.resolve())) for r in roots)
    except Exception:
        return False


def cap_fs_read(path: str, roots: list[Path], max_bytes: int = 400_000) -> dict:
    p = Path(path).expanduser()
    if not _path_in(roots, p):
        return {"error": "path outside allowed roots"}
    if not p.exists():
        return {"error": "no such file"}
    if p.is_dir():
        entries = []
        for item in sorted(p.iterdir())[:500]:
            entries.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            })
        return {"dir": str(p), "entries": entries}
    data = p.read_bytes()[:max_bytes]
    try:
        return {"file": str(p), "text": data.decode("utf-8"),
                "size": p.stat().st_size, "truncated": len(data) == max_bytes}
    except UnicodeDecodeError:
        return {"file": str(p), "b64": base64.b64encode(data).decode(),
                "size": p.stat().st_size}


def cap_fs_write(path: str, content: str, roots: list[Path],
                 backup: bool = True) -> dict:
    p = Path(path).expanduser()
    if not _path_in(roots, p):
        return {"error": "path outside allowed roots"}
    if backup and p.exists():
        bak = p.with_suffix(p.suffix + ".bak")
        bak.write_bytes(p.read_bytes())
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    _audit("fs_write", "remote", "ok", {"path": str(p), "bytes": len(content)})
    return {"written": str(p), "bytes": len(content), "backup": backup and p.exists()}


def cap_fs_list_tree(path: str, roots: list[Path], depth: int = 3) -> dict:
    """Recursive directory tree, depth-limited."""
    p = Path(path).expanduser()
    if not _path_in(roots, p):
        return {"error": "path outside allowed roots"}

    def _tree(node: Path, d: int) -> dict:
        if d == 0 or not node.is_dir():
            return {"name": node.name, "type": "file", "size": node.stat().st_size if node.is_file() else 0}
        children = []
        try:
            for child in sorted(node.iterdir())[:100]:
                children.append(_tree(child, d - 1))
        except PermissionError:
            pass
        return {"name": node.name, "type": "dir", "children": children}

    return _tree(p, depth)


def cap_clipboard_read() -> dict:
    try:
        import pyperclip
        text = pyperclip.paste()
        _audit("clipboard_read", "remote", "ok", {"chars": len(text)})
        return {"text": text, "chars": len(text)}
    except ImportError:
        return {"error": "pip install pyperclip"}


def cap_clipboard_write(text: str) -> dict:
    try:
        import pyperclip
        pyperclip.copy(text)
        _audit("clipboard_write", "remote", "ok", {"chars": len(text)})
        return {"copied_chars": len(text)}
    except ImportError:
        return {"error": "pip install pyperclip"}


def cap_notify(title: str, body: str, urgency: str = "normal") -> dict:
    try:
        system = platform.system()
        if system == "Windows":
            try:
                from win10toast import ToastNotifier
                ToastNotifier().show_toast(title, body, duration=5, threaded=True)
                return {"ok": True, "via": "win10toast"}
            except ImportError:
                pass
            # fallback: PowerShell toast
            ps = (
                f'Add-Type -AssemblyName System.Windows.Forms; '
                f'[System.Windows.Forms.MessageBox]::Show("{body}", "{title}")'
            )
            subprocess.Popen(["powershell", "-Command", ps])
            return {"ok": True, "via": "powershell"}
        if system == "Darwin":
            subprocess.run([
                "osascript", "-e",
                f'display notification "{body}" with title "{title}"',
            ], timeout=5)
            return {"ok": True, "via": "osascript"}
        if system == "Linux":
            for cmd in (["notify-send", f"--urgency={urgency}", title, body],
                        ["zenity", "--notification", f"--text={title}: {body}"]):
                if shutil.which(cmd[0]):
                    subprocess.run(cmd, timeout=5)
                    return {"ok": True, "via": cmd[0]}
        print(f"\a[GH05T3] {title}: {body}")
        return {"ok": True, "via": "console"}
    except Exception as e:
        return {"error": str(e)}


def cap_env_info() -> dict:
    """Rich environment snapshot."""
    info: dict[str, Any] = {
        "host": platform.node(),
        "os": platform.system(),
        "os_release": platform.release(),
        "arch": platform.machine(),
        "python": sys.version.split()[0],
        "cwd": str(Path.cwd()),
        "home": str(Path.home()),
        "session_id": _SESSION_ID,
    }
    if HAS_PSUTIL:
        mem = psutil.virtual_memory()
        info["ram_gb"] = round(mem.total / 1e9, 1)
        info["cpu_count"] = psutil.cpu_count()
    return info


# ═══════════════════════════════════════════════════════════════════
# GhostEye — enhanced with diff detection
# ═══════════════════════════════════════════════════════════════════
def _ocr_png_b64(png_b64: str) -> str:
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(io.BytesIO(base64.b64decode(png_b64)))
        return pytesseract.image_to_string(img)[:5000]
    except ImportError:
        return ""
    except Exception as e:
        LOG.warning("OCR failed: %s", e)
        return ""


def _active_app_title() -> str:
    try:
        system = platform.system()
        if system == "Windows":
            import ctypes
            user32 = ctypes.windll.user32
            h = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(h)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(h, buff, length + 1)
            return buff.value[:120]
        if system == "Darwin":
            out = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=2,
            )
            return (out.stdout or "").strip()[:120]
        if system == "Linux":
            for tool in ["xdotool", "wmctrl"]:
                if shutil.which(tool):
                    args = (["xdotool", "getactivewindow", "getwindowname"]
                            if tool == "xdotool" else ["wmctrl", "-a", ":ACTIVE:"])
                    out = subprocess.run(args, capture_output=True, text=True, timeout=2)
                    return (out.stdout or "").strip()[:120]
    except Exception:
        pass
    return ""


async def _ghosteye_loop(ws, enabled_flag: dict, interval: int, ocr: bool):
    LOG.info("GhostEye online — interval=%ds ocr=%s", interval, ocr)
    _last_hash = ""
    while True:
        try:
            await asyncio.sleep(interval)
            if not enabled_flag["v"]:
                continue
            frame = cap_screenshot()
            if "error" in frame:
                continue
            # Change detection — only push if screen changed (hash of first 500 bytes of b64)
            frame_thumb = frame["png_b64"][:500]
            frame_hash = hashlib.md5(frame_thumb.encode()).hexdigest()
            changed = frame_hash != _last_hash
            _last_hash = frame_hash

            text = _ocr_png_b64(frame["png_b64"]) if ocr else ""
            active_app = _active_app_title()
            await ws.send(json.dumps({
                "event": "ghosteye_frame",
                "data": {
                    "png_b64": frame["png_b64"],
                    "w": frame.get("w"), "h": frame.get("h"),
                    "text": text,
                    "active_app": active_app,
                    "changed": changed,
                    "frame_hash": frame_hash,
                },
            }))
        except asyncio.CancelledError:
            break
        except Exception:
            LOG.exception("ghosteye frame error")


# ═══════════════════════════════════════════════════════════════════
# CENTRAL DISPATCH
# ═══════════════════════════════════════════════════════════════════
_VAULT = GhostVault()  # initialized at module level; key set in main()

def _dispatch(action: str, args: dict, cfg: AgentConfig) -> dict:
    _log_args = {k: (v if len(str(v)) < 80 else f"<{len(str(v))}B>") for k, v in args.items()}
    LOG.info("▶ %s %s", action, _log_args)

    caps = cfg.caps
    fr = cfg.fs_read_roots
    fw = cfg.fs_write_roots
    allow_any = cfg.allow_any_shell

    # ── Screen ────────────────────────────────────────────────────
    if action == "screenshot":
        if "screen_read" not in caps:
            return {"error": "screen_read not granted"}
        return cap_screenshot(monitor=args.get("monitor", 1))

    # ── Shell ─────────────────────────────────────────────────────
    if action == "shell":
        if "shell_exec" not in caps:
            return {"error": "shell_exec not granted"}
        return cap_shell(args.get("cmd", ""), allowlist=not allow_any,
                         timeout=int(args.get("timeout", 30)),
                         cwd=args.get("cwd"))

    # ── Filesystem ────────────────────────────────────────────────
    if action == "fs_read":
        if "fs_read" not in caps:
            return {"error": "fs_read not granted"}
        return cap_fs_read(args.get("path", ""), fr)

    if action == "fs_write":
        if "fs_write" not in caps:
            return {"error": "fs_write not granted"}
        return cap_fs_write(args.get("path", ""), args.get("content", ""), fw,
                            backup=args.get("backup", True))

    if action == "fs_tree":
        if "fs_read" not in caps:
            return {"error": "fs_read not granted"}
        return cap_fs_list_tree(args.get("path", str(Path.home())), fr,
                                depth=int(args.get("depth", 3)))

    # ── Clipboard ─────────────────────────────────────────────────
    if action == "clipboard_read":
        if "clipboard" not in caps:
            return {"error": "clipboard not granted"}
        return cap_clipboard_read()

    if action == "clipboard_write":
        if "clipboard" not in caps:
            return {"error": "clipboard not granted"}
        return cap_clipboard_write(args.get("text", ""))

    # ── Notify ────────────────────────────────────────────────────
    if action == "notify":
        if "notify" not in caps:
            return {"error": "notify not granted"}
        return cap_notify(args.get("title", "GH05T3"), args.get("body", ""),
                          args.get("urgency", "normal"))

    # ── Mic ───────────────────────────────────────────────────────
    if action == "mic_capture":
        if "mic" not in caps:
            return {"error": "mic not granted"}
        return cap_mic_capture(duration_s=int(args.get("duration_s", 5)),
                               model_path=args.get("vosk_model", "vosk-model"))

    # ── Process manager ───────────────────────────────────────────
    if action == "proc_launch":
        return cap_proc_launch(args.get("name", "proc"), args.get("cmd", ""), caps)

    if action == "proc_status":
        return cap_proc_status()

    if action == "proc_kill":
        return cap_proc_kill(args.get("name", ""))

    # ── Memory ────────────────────────────────────────────────────
    if action == "memory_store":
        MEMORY.remember(args.get("key", "note"), args.get("value"), args.get("tags", ""))
        return {"stored": args.get("key")}

    if action == "memory_recall":
        return {"memories": MEMORY.recall(args.get("key", ""), limit=int(args.get("limit", 5)))}

    if action == "memory_recent":
        return {"memories": MEMORY.recall_recent(limit=int(args.get("limit", 20)))}

    # ── Vault ─────────────────────────────────────────────────────
    if action == "vault_put":
        return _VAULT.put(args.get("name", ""), args.get("secret", ""))

    if action == "vault_get":
        return _VAULT.get(args.get("name", ""))

    if action == "vault_list":
        return _VAULT.list_keys()

    # ── System health ─────────────────────────────────────────────
    if action == "sys_health":
        return _collect_health()

    if action == "env_info":
        return cap_env_info()

    # ── Audit log export ─────────────────────────────────────────
    if action == "audit_tail":
        n = int(args.get("n", 20))
        try:
            lines = AUDIT_LOG.read_text().splitlines()[-n:]
            return {"entries": [json.loads(l) for l in lines if l.strip()]}
        except FileNotFoundError:
            return {"entries": []}

    return {"error": f"unknown action '{action}'"}


# ═══════════════════════════════════════════════════════════════════
# MAIN CONNECTION LOOP
# ═══════════════════════════════════════════════════════════════════
async def run(cfg: AgentConfig):
    parsed = urlparse(cfg.gateway)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    ws_url = f"{scheme}://{parsed.netloc}/api/companion/ws"
    LOG.info("Connecting → %s  label=%s  caps=%s", ws_url, cfg.label, sorted(cfg.caps))

    handshake = {
        "token": cfg.token,
        "label": cfg.label,
        "version": "2.0.0",
        "session_id": _SESSION_ID,
        "capabilities": sorted(cfg.caps),
        "features": {
            "react": cfg.react_enabled,
            "memory": True,
            "vault": HAS_CRYPTO,
            "health_beacon": HAS_PSUTIL,
            "ghosteye": cfg.ghosteye,
            "llm_port": cfg.llm_port,
            "proc_manager": True,
        },
        "info": {
            "os": platform.system(),
            "release": platform.release(),
            "arch": platform.machine(),
            "python": sys.version.split()[0],
            "hostname": platform.node(),
        },
    }

    backoff = 2
    eye_enabled = {"v": cfg.ghosteye}

    while True:
        try:
            async with websockets.connect(ws_url, max_size=32 * 1024 * 1024,
                                          ping_interval=30, ping_timeout=10) as ws:
                await ws.send(json.dumps(handshake))
                hello = json.loads(await ws.recv())
                LOG.info("✓ Paired: %s", hello)
                _audit("connect", "agent", "ok", {"gateway": cfg.gateway, "label": cfg.label})
                backoff = 2

                tasks = []

                if cfg.ghosteye and "screen_read" in cfg.caps:
                    tasks.append(asyncio.create_task(
                        _ghosteye_loop(ws, eye_enabled, cfg.ghosteye_interval, cfg.ghosteye_ocr)
                    ))

                if HAS_PSUTIL and cfg.health_interval > 0:
                    tasks.append(asyncio.create_task(
                        _health_beacon_loop(ws, cfg.health_interval)
                    ))

                try:
                    async for raw in ws:
                        msg = json.loads(raw)

                        # Control messages
                        ctrl = msg.get("control")
                        if ctrl == "ghosteye":
                            eye_enabled["v"] = bool(msg.get("enabled"))
                            LOG.info("GhostEye %s via control", "ON" if eye_enabled["v"] else "OFF")
                            continue
                        if ctrl == "ping":
                            await ws.send(json.dumps({"pong": True, "ts": time.time()}))
                            continue

                        rid = msg.get("req_id")
                        action = msg.get("action")
                        args = msg.get("args") or {}

                        # ReAct delegation
                        if action == "react" and cfg.react_enabled:
                            goal = args.get("goal", "")
                            result = await react_loop(
                                goal,
                                lambda a, a2, c=cfg: _dispatch(a, a2, c),
                                cfg.llm_port,
                                max_steps=int(args.get("max_steps", 6)),
                            )
                        else:
                            result = _dispatch(action, args, cfg)

                        try:
                            await ws.send(json.dumps({"req_id": rid, "result": result}))
                        except Exception:
                            LOG.exception("send failed")

                finally:
                    for t in tasks:
                        t.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            LOG.warning("Connection error: %s — retry in %ds", e, backoff)
            _audit("disconnect", "agent", "retry", {"error": str(e), "backoff": backoff})
            await asyncio.sleep(backoff)
            backoff = min(120, int(backoff * 1.8))


# ═══════════════════════════════════════════════════════════════════
# CLAIM TOKEN
# ═══════════════════════════════════════════════════════════════════
def _claim(gateway: str, code: str, label: str) -> str:
    import urllib.request
    import urllib.parse
    url = (f"{gateway.rstrip('/')}/api/companion/claim"
           f"?code={urllib.parse.quote(code)}&label={urllib.parse.quote(label)}")
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)["token"]


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════
def _parse_args():
    p = argparse.ArgumentParser(
        description="GH05T3 Sovereign Companion Agent v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Connection
    p.add_argument("--gateway", default=os.environ.get("GHOST_GATEWAY_URL", ""))
    p.add_argument("--pair-code", default=os.environ.get("PAIR_CODE", ""))
    p.add_argument("--label", default=platform.node())

    # Capabilities
    p.add_argument("--screen-read", action="store_true")
    p.add_argument("--shell-exec", action="store_true")
    p.add_argument("--allow-any-shell", action="store_true", help="DANGEROUS: bypasses allowlist")
    p.add_argument("--fs-read", action="append", default=[])
    p.add_argument("--fs-write", action="append", default=[])
    p.add_argument("--clipboard", action="store_true")
    p.add_argument("--notify", action="store_true", default=True)
    p.add_argument("--mic", action="store_true")
    p.add_argument("--all", action="store_true", help="Grant all capabilities")

    # GhostEye
    p.add_argument("--ghosteye", action="store_true")
    p.add_argument("--ghosteye-interval", type=int, default=15)
    p.add_argument("--ghosteye-ocr", action="store_true")

    # New v2 flags
    p.add_argument("--llm-port", type=int, default=int(os.environ.get("SOVEREIGN_GATEWAY_PORT", 8000)),
                   help="Port for local Sovereign Core LLM gateway (default 8000)")
    p.add_argument("--react", action="store_true",
                   help="Enable ReAct reasoning loop (requires local LLM)")
    p.add_argument("--health-interval", type=int, default=60,
                   help="Seconds between health beacon pushes (0=disable)")
    p.add_argument("--vault-key", default=os.environ.get("GHOST_VAULT_KEY", ""),
                   help="Base64 Fernet key for credential vault")

    return p.parse_args()


def main():
    args = _parse_args()

    if HAS_RICH:
        _console.rule("[bold cyan]GH05T3 SOVEREIGN COMPANION v2.0[/]")
    else:
        print("=" * 60)
        print("  GH05T3 SOVEREIGN COMPANION AGENT v2.0")
        print("=" * 60)

    gateway = args.gateway or input("Gateway URL: ").strip()
    code = args.pair_code or input("Pairing code: ").strip()
    token = _claim(gateway, code, args.label)
    LOG.info("Token acquired ✓")

    caps: set[str] = set()
    if args.all:
        caps = {"screen_read", "shell_exec", "fs_read", "fs_write",
                "clipboard", "notify", "mic"}
    else:
        if args.screen_read: caps.add("screen_read")
        if args.shell_exec:  caps.add("shell_exec")
        if args.fs_read:     caps.add("fs_read")
        if args.fs_write:    caps.add("fs_write")
        if args.clipboard:   caps.add("clipboard")
        if args.notify:      caps.add("notify")
        if args.mic:         caps.add("mic")

    fs_read_roots = [Path(p).expanduser() for p in args.fs_read] or [Path.home()]
    fs_write_roots = [Path(p).expanduser() for p in args.fs_write]

    vault_key: bytes | None = None
    if args.vault_key and HAS_CRYPTO:
        try:
            vault_key = args.vault_key.encode()
            global _VAULT
            _VAULT = GhostVault(key=vault_key)
        except Exception as e:
            LOG.warning("Bad vault key: %s — generating new one", e)

    cfg = AgentConfig(
        gateway=gateway,
        token=token,
        label=args.label,
        caps=caps,
        fs_read_roots=fs_read_roots,
        fs_write_roots=fs_write_roots,
        allow_any_shell=args.allow_any_shell,
        ghosteye=args.ghosteye or args.all,
        ghosteye_interval=args.ghosteye_interval,
        ghosteye_ocr=args.ghosteye_ocr,
        llm_port=args.llm_port,
        react_enabled=args.react,
        health_interval=args.health_interval,
        vault_key=vault_key,
    )

    LOG.info("Session %s | caps=%s | react=%s | llm_port=%d",
             _SESSION_ID, sorted(caps), cfg.react_enabled, cfg.llm_port)

    # Global kill switch
    try:
        import keyboard
        def _kill():
            LOG.warning("Kill switch triggered — shutting down")
            _audit("killswitch", "operator", "shutdown", {})
            os._exit(0)
        keyboard.add_hotkey("ctrl+shift+k", _kill)
        LOG.info("Kill switch armed: Ctrl+Shift+K")
    except Exception:
        pass

    try:
        asyncio.run(run(cfg))
    except KeyboardInterrupt:
        _audit("stop", "operator", "keyboard_interrupt", {})
        LOG.info("Companion stopped ✓")


if __name__ == "__main__":
    main()
