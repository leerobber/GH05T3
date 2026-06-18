#!/usr/bin/env python3
"""
GH05T3 core stack launcher — clean restart, port review, health-gated startup.

Ports managed:
  27017  MongoDB
  8001   backend/server.py
  8002   backend/gateway_v3.py
  3210   frontend static bundle
  8010   gh05t3_inference.py (optional — skipped if torch missing)

Usage:
    python run_stack.py              # stop core ports, start stack, open browser
    python run_stack.py --stop       # stop core stack only
    python run_stack.py --review     # print port table, exit
    python run_stack.py --no-browser # start without opening dashboard
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.resolve()
FRONTEND_DIR = ROOT / "frontend"
BUILD_DIR = FRONTEND_DIR / "build"
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
PIDFILE = ROOT / "data" / "run_stack.pid"
SUPERVISOR_PIDFILE = ROOT / "data" / "supervisor.pid"

CORE_PORTS = {
    "mongo": 27017,
    "backend": 8001,
    "gateway": 8002,
    "frontend": 3210,
    "inference": 8010,
}

OPTIONAL_PORTS = {
    "ollama": 11434,
    "lemonade": 13305,
}


def _find_py() -> Path:
    for candidate in (
        ROOT / "backend" / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / "venv" / "Scripts" / "python.exe",
        Path(r"C:\Users\leer4\AppData\Local\Programs\Python\Python312\python.exe"),
    ):
        if candidate.exists():
            return candidate
    return Path(sys.executable)


PY = _find_py()


def _tcp_open(port: int, timeout: float = 1.0) -> bool:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_ok(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status < 500
    except Exception:
        return False


def _kill_port(port: int) -> list[int]:
    """Kill listeners on a port (any bind address). Returns PIDs killed."""
    killed: list[int] = []
    try:
        out = subprocess.check_output(
            f'netstat -ano 2>nul | findstr "LISTENING" | findstr ":{port} "',
            shell=True,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for line in out.strip().splitlines():
            parts = line.split()
            if not parts:
                continue
            pid = parts[-1]
            if pid.isdigit() and pid != "0" and int(pid) not in killed:
                subprocess.run(
                    f"taskkill /F /PID {pid}",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                killed.append(int(pid))
    except Exception:
        pass
    return killed


def _read_env(key: str) -> str:
    env_path = ROOT / "backend" / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip().lower() == key.lower():
            return v.strip().strip('"').strip("'")
    return ""


def _tailscale_ip() -> str:
    try:
        out = subprocess.check_output(
            ["tailscale", "ip", "--4"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
        return out.splitlines()[0] if out else ""
    except Exception:
        return ""


def _remote_ip() -> str:
    ts = _tailscale_ip()
    if ts:
        return ts
    try:
        out = subprocess.check_output("ipconfig", text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            if "IPv4" in line and "192.168." in line:
                return line.split(":")[-1].strip()
    except Exception:
        pass
    return "localhost"


def _supervisor_running() -> bool:
    if not SUPERVISOR_PIDFILE.exists():
        return False
    try:
        pid = int(SUPERVISOR_PIDFILE.read_text().strip())
        out = subprocess.check_output(
            f'tasklist /FI "PID eq {pid}" /FO CSV /NH',
            shell=True,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return "python" in out.lower()
    except Exception:
        return False


def _frontend_build_ok() -> bool:
    index = BUILD_DIR / "index.html"
    if not index.is_file():
        return False
    html = index.read_text(encoding="utf-8", errors="ignore")
    refs = re.findall(r'/(assets/[^"\']+)', html)
    if not refs:
        return False
    return all((BUILD_DIR / ref.lstrip("/")).is_file() for ref in refs)


def _build_frontend() -> tuple[bool, str]:
    """Run yarn build in frontend/. Returns (ok, message)."""
    if not (FRONTEND_DIR / "package.json").is_file():
        return False, "frontend/package.json missing"
    yarn = shutil.which("yarn")
    if not yarn:
        return False, "yarn not found — install Node.js + yarn"
    if not (FRONTEND_DIR / "node_modules").is_dir():
        print("  Installing frontend dependencies...")
        install = subprocess.run(
            "yarn install --frozen-lockfile",
            cwd=str(FRONTEND_DIR),
            capture_output=True,
            text=True,
            shell=True,
        )
        if install.returncode != 0:
            tail = (install.stderr or install.stdout or "")[-400:]
            return False, f"yarn install failed: {tail}"

    print("  Building frontend (vite)...")
    proc = subprocess.run(
        "yarn build",
        cwd=str(FRONTEND_DIR),
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        shell=True,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-400:]
        return False, f"yarn build failed: {tail}"
    if not _frontend_build_ok():
        return False, "build finished but index.html assets are missing"
    return True, "built"


def _ensure_frontend(build: bool) -> tuple[bool, str]:
    if _frontend_build_ok():
        return True, "ok (existing build)"
    if not build:
        return False, "frontend/build stale or missing — run with --build"
    ok, msg = _build_frontend()
    return ok, msg


def _inference_available() -> bool:
    proc = subprocess.run(
        [str(PY), "-c", "import torch"],
        capture_output=True,
        cwd=str(ROOT / "backend"),
    )
    return proc.returncode == 0


def _log_path(name: str) -> Path:
    return LOGS / f"{name}.log"


def _win_flags() -> int:
    # Detach so services keep running after run_stack.py exits.
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    flags |= getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
    flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    return flags


def _spawn(name: str, cmd: list, cwd: Path, extra_env: Optional[dict] = None) -> subprocess.Popen:
    log_file = open(_log_path(name), "a", encoding="utf-8", buffering=1)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("AETHYRO_SKIP_LICENSE", "1")
    if extra_env:
        env.update(extra_env)
    return subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=log_file,
        stderr=log_file,
        env=env,
        creationflags=_win_flags() if sys.platform == "win32" else 0,
    )


_procs: dict[str, subprocess.Popen] = {}


def _wait_health(name: str, proc: subprocess.Popen, check, timeout: int) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return f"failed (exited {proc.returncode}, see logs/{name}.log)"
        if check():
            return "up"
        time.sleep(0.5)
    if proc.poll() is None:
        return "degraded (health timeout)"
    return f"failed (exited {proc.returncode})"


def _ensure_ollama() -> str:
    try:
        out = subprocess.check_output(
            'tasklist /FI "IMAGENAME eq ollama.exe" /FO CSV /NH',
            shell=True,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        if "ollama.exe" in out.lower():
            return "already running"
    except Exception:
        pass
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    for _ in range(20):
        if _tcp_open(OPTIONAL_PORTS["ollama"]):
            return "started"
        time.sleep(0.5)
    return "starting (not ready yet)"


def _load_lemonade() -> str:
    lemonade = Path(os.environ.get("LOCALAPPDATA", "")) / "lemonade_server" / "bin" / "lemonade.exe"
    if not lemonade.exists():
        return "skip (not installed)"
    subprocess.Popen(
        [str(lemonade), "load", "Gemma-4-E2B-it-GGUF"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    return "loading in background"


def review_ports() -> dict:
    rows = {}
    for name, port in {**CORE_PORTS, **OPTIONAL_PORTS}.items():
        rows[name] = {
            "port": port,
            "listening": _tcp_open(port),
        }
    return rows


def print_port_review():
    remote = _remote_ip()
    rows = review_ports()
    print("\n=== GH05T3 Port Review ===\n")
    print(f"{'SERVICE':<12}  {'PORT':<6}  {'STATUS':<12}  NOTES")
    print("-" * 60)
    notes = {
        "mongo": "MongoDB — backend persistence",
        "backend": "server.py — economy, Telegram, CFO",
        "gateway": "gateway_v3 — SwarmBus, MCP, agents",
        "frontend": "React build — dashboard UI",
        "inference": "LoRA model — needs torch in venv",
        "ollama": "Local LLM fallback",
        "lemonade": "AMD 780M iGPU — chat/STT/TTS",
    }
    for name in list(CORE_PORTS) + list(OPTIONAL_PORTS):
        port = rows[name]["port"]
        status = "LISTENING" if rows[name]["listening"] else "DOWN"
        print(f"{name:<12}  {port:<6}  {status:<12}  {notes.get(name, '')}")
    print(f"\nRemote IP: {remote}")
    print(f"Python:    {PY}")
    print(f"Logs:      {LOGS}")
    if _supervisor_running():
        print("\n[!] supervisor.py is running — ops tools will not duplicate")
    print()


def stop_stack(kill_mongo: bool = True):
    print("Stopping GH05T3 core stack...")
    for proc in list(_procs.values()):
        if proc.poll() is None:
            subprocess.run(
                f"taskkill /F /T /PID {proc.pid}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    ports = [CORE_PORTS["backend"], CORE_PORTS["gateway"], CORE_PORTS["frontend"], CORE_PORTS["inference"]]
    if kill_mongo:
        ports.insert(0, CORE_PORTS["mongo"])

    for port in ports:
        killed = _kill_port(port)
        if killed:
            print(f"  port {port}: killed PID(s) {killed}")
        elif _tcp_open(port):
            print(f"  port {port}: still occupied")
        else:
            print(f"  port {port}: clear")

    PIDFILE.unlink(missing_ok=True)
    print("Done.\n")


def _core_ok(results: list[tuple[str, str, str]]) -> bool:
    by_name = {name: status for name, _, status in results}
    required = ("mongo", "backend", "gateway", "frontend")
    ok_prefixes = ("up", "started", "already", "loading", "ok")
    for svc in required:
        status = by_name.get(svc, "")
        if not any(status.startswith(p) for p in ok_prefixes):
            return False
    return True


def start_stack(open_browser: bool = True, build: bool = False) -> int:
    if PIDFILE.exists():
        try:
            old = int(PIDFILE.read_text().strip())
            out = subprocess.check_output(
                f'tasklist /FI "PID eq {old}" /FO CSV /NH',
                shell=True,
                text=True,
                stderr=subprocess.DEVNULL,
            )
            if "python" in out.lower():
                print(f"run_stack already running (pid={old}). Use --stop first.")
                return 1
        except Exception:
            pass

    PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    PIDFILE.write_text(str(os.getpid()))

    print("=== GH05T3 Stack Start ===\n")
    print(f"Python: {PY}\n")

    # Clean restart — core API/UI ports only; mongo handled below
    for port in (CORE_PORTS["backend"], CORE_PORTS["gateway"], CORE_PORTS["frontend"], CORE_PORTS["inference"]):
        _kill_port(port)
    time.sleep(0.5)

    results: list[tuple[str, str, str]] = []

    # MongoDB
    if _tcp_open(CORE_PORTS["mongo"]):
        results.append(("mongo", str(CORE_PORTS["mongo"]), "up (existing)"))
    else:
        (ROOT / "mongo-data").mkdir(exist_ok=True)
        proc = _spawn(
            "mongo",
            ["mongod", "--dbpath", str(ROOT / "mongo-data"), "--port", "27017", "--bind_ip", "127.0.0.1", "--quiet"],
            ROOT,
        )
        _procs["mongo"] = proc
        status = _wait_health("mongo", proc, lambda: _tcp_open(CORE_PORTS["mongo"]), 20)
        results.append(("mongo", str(CORE_PORTS["mongo"]), status))

    # Ollama + Lemonade (non-blocking)
    ollama_status = _ensure_ollama()
    lemonade_status = _load_lemonade()
    results.append(("ollama", str(OPTIONAL_PORTS["ollama"]), ollama_status))
    results.append(("lemonade", str(OPTIONAL_PORTS["lemonade"]), lemonade_status))

    ts_ip = _tailscale_ip()
    extra = {"TAILSCALE_OWN_IP": ts_ip} if ts_ip else {}

    # Backend
    proc = _spawn(
        "backend",
        [str(PY), "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"],
        ROOT / "backend",
    )
    _procs["backend"] = proc
    status = _wait_health("backend", proc, lambda: _http_ok("http://localhost:8001/api/health"), 30)
    results.append(("backend", "8001", status))

    # Gateway
    proc = _spawn(
        "gateway",
        [str(PY), "-m", "uvicorn", "gateway_v3:app", "--host", "0.0.0.0", "--port", "8002"],
        ROOT / "backend",
        extra_env=extra,
    )
    _procs["gateway"] = proc
    status = _wait_health("gateway", proc, lambda: _http_ok("http://localhost:8002/health"), 30)
    results.append(("gateway", "8002", status))

    # Frontend — verify production build before serving
    build_ok, build_msg = _ensure_frontend(build=build)
    if not build_ok:
        results.append(("frontend", "3210", f"failed ({build_msg})"))
    else:
        if build_msg != "ok (existing build)":
            results.append(("frontend-build", "—", build_msg))
        proc = _spawn(
            "frontend",
            [str(PY), "-m", "http.server", "3210", "--directory", str(BUILD_DIR)],
            ROOT,
        )
        _procs["frontend"] = proc
        status = _wait_health("frontend", proc, lambda: _http_ok("http://localhost:3210/"), 10)
        results.append(("frontend", "3210", status))

    # Inference (optional)
    if _inference_available():
        proc = _spawn("inference", [str(PY), "gh05t3_inference.py"], ROOT / "backend")
        _procs["inference"] = proc
        status = _wait_health("inference", proc, lambda: _tcp_open(CORE_PORTS["inference"]), 120)
        results.append(("inference", "8010", status))
    else:
        results.append(("inference", "8010", "skip (torch not in venv — use Ollama)"))

    # Voice listener (non-critical)
    voice = ROOT / "whisper_listener.py"
    if voice.exists():
        proc = _spawn("voice", [str(PY), str(voice)], ROOT)
        _procs["voice"] = proc
        results.append(("voice", "—", "started" if proc.poll() is None else "failed"))

    # Training ops — only if enabled and supervisor is not already managing them
    if _read_env("ENABLE_OPS") == "1" and not _supervisor_running():
        for name, script in (("herald", "herald.py --console"), ("cmd-listener", "cmd_listener.py")):
            parts = script.split()
            if (ROOT / parts[0]).exists():
                proc = _spawn(name, [str(PY), *parts], ROOT)
                _procs[name] = proc
                results.append((name, "—", "started" if proc.poll() is None else "failed"))
    elif _read_env("ENABLE_OPS") == "1":
        results.append(("ops", "—", "skip (supervisor running)"))

    remote = _remote_ip()
    token = _read_env("GH05T3_API_TOKEN")

    print(f"\n{'SERVICE':<12}  {'PORT':<6}  STATUS")
    print("-" * 40)
    for name, port, status in results:
        print(f"{name:<12}  {port:<6}  {status}")

    print("\n--- URLs ---")
    print(f"  Dashboard  : http://localhost:3210")
    print(f"  Remote     : http://{remote}:3210")
    print(f"  Gateway    : http://{remote}:8002")
    print(f"  Backend    : http://{remote}:8001")
    print(f"  MCP (SSE)  : http://{remote}:8002/mcp/sse")
    print(f"  Lemonade   : http://localhost:13305")
    print(f"  Logs       : {LOGS}")

    if not token:
        print("\n  [!] OPEN MODE — set GH05T3_API_TOKEN in backend/.env")
    else:
        print("\n  [OK] API token configured")

    if ts_ip:
        print(f"  [OK] Tailscale: {ts_ip}")
    else:
        print("  [!] Tailscale not detected — LAN only")

    if open_browser and _http_ok("http://localhost:3210/"):
        webbrowser.open("http://localhost:3210")

    print("\nStack running. Logs in logs/. Use stop.bat or: python run_stack.py --stop\n")
    return 0 if _core_ok(results) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="GH05T3 core stack launcher")
    ap.add_argument("--stop", action="store_true", help="stop core stack")
    ap.add_argument("--review", action="store_true", help="print port status table")
    ap.add_argument("--build", action="store_true", help="build frontend before start")
    ap.add_argument("--no-browser", action="store_true", help="do not open dashboard")
    ap.add_argument("--keep-mongo", action="store_true", help="on --stop, leave MongoDB running")
    args = ap.parse_args()

    if args.review:
        print_port_review()
        fb = "OK" if _frontend_build_ok() else "MISSING/STALE"
        print(f"Frontend build: {fb}  ({BUILD_DIR})")
        print()
        return 0
    if args.stop:
        stop_stack(kill_mongo=not args.keep_mongo)
        return 0
    return start_stack(open_browser=not args.no_browser, build=args.build)


if __name__ == "__main__":
    raise SystemExit(main())