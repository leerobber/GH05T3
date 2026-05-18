"""
GH05T3 + Sovereign Economy — Process Supervisor
================================================
Single entry point for everything. No terminal windows.
All output → logs/  Auto-restarts crashed services.
Status API → http://localhost:8090/status

Usage:
    python supervisor.py            # start everything
    python supervisor.py --stop     # kill everything
    python supervisor.py --status   # print status and exit
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
import urllib.request

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).parent.resolve()
ECO_DIR = Path(r"C:\Users\leer4\Documents\agent-economy")
LOGS    = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

GH_PY  = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
ECO_PY = ECO_DIR / "venv" / "Scripts" / "python.exe"

if not GH_PY.exists():
    GH_PY = Path(sys.executable)
if not ECO_PY.exists():
    ECO_PY = Path(sys.executable)

STATUS_PORT = 8090

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[
        logging.FileHandler(LOGS / "supervisor.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("supervisor")

# ── Service definitions ────────────────────────────────────────────────────────
# order matters — services start in list order, each waits for the previous
SERVICES = [
    {
        "name":    "economy-api",
        "cmd":     [str(ECO_PY), "start.py"],
        "cwd":     str(ECO_DIR),
        "port":    8081,
        "health":  "http://localhost:8081/system/stats",
        "timeout": 30,     # seconds to wait for health check on first start
        "restart": True,
    },
    {
        "name":    "auto-runner",
        "cmd":     [str(ECO_PY), "auto_runner.py", "--batch", "10",
                    "--interval", "0.5", "--export-every", "50"],
        "cwd":     str(ECO_DIR),
        "port":    None,
        "health":  None,
        "timeout": 3,
        "restart": True,
    },
    {
        "name":    "mongo",
        "cmd":     ["mongod", "--dbpath", str(ROOT / "mongo-data"),
                    "--port", "27017", "--bind_ip", "127.0.0.1"],
        "cwd":     str(ROOT),
        "port":    27017,
        "health":  None,           # TCP check
        "timeout": 10,
        "restart": True,
    },
    {
        "name":    "backend",
        "cmd":     [str(GH_PY), "-m", "uvicorn", "server:app",
                    "--host", "0.0.0.0", "--port", "8001"],
        "cwd":     str(ROOT / "backend"),
        "port":    8001,
        "health":  "http://localhost:8001/api/health",
        "timeout": 20,
        "restart": True,
    },
    {
        "name":    "gateway",
        "cmd":     [str(GH_PY), "-m", "uvicorn", "gateway_v3:app",
                    "--host", "0.0.0.0", "--port", "8002"],
        "cwd":     str(ROOT / "backend"),
        "port":    8002,
        "health":  "http://localhost:8002/health",
        "timeout": 20,
        "restart": True,
    },
    {
        "name":    "frontend",
        "cmd":     [str(GH_PY), "-m", "http.server", "3210",
                    "--directory", str(ROOT / "frontend" / "build")],
        "cwd":     str(ROOT),
        "port":    3210,
        "health":  "http://localhost:3210",
        "timeout": 5,
        "restart": True,
    },
]

# ── State ──────────────────────────────────────────────────────────────────────
_state: dict[str, dict] = {
    s["name"]: {
        "status":        "stopped",   # stopped|starting|running|degraded|restarting
        "pid":           None,
        "restarts":      0,
        "last_restart":  0.0,
        "last_healthy":  0.0,
    }
    for s in SERVICES
}

_procs:  dict[str, Optional[subprocess.Popen]] = {s["name"]: None for s in SERVICES}
_stop_event = threading.Event()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _log_path(name: str) -> Path:
    return LOGS / f"{name}.log"


def _tcp_open(port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_ok(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status < 500
    except Exception:
        return False


def _is_healthy(svc: dict) -> bool:
    health = svc.get("health")
    port   = svc.get("port")
    if health:
        return _http_ok(health)
    if port:
        return _tcp_open(port)
    # no check defined — consider healthy if process is alive
    proc = _procs.get(svc["name"])
    return proc is not None and proc.poll() is None


def _kill_port(port: int):
    """Kill whatever is listening on a port (Windows)."""
    try:
        out = subprocess.check_output(
            f'netstat -ano 2>nul | findstr "0.0.0.0:{port} "',
            shell=True, text=True, stderr=subprocess.DEVNULL,
        )
        for line in out.strip().splitlines():
            parts = line.split()
            if parts:
                pid = parts[-1]
                if pid.isdigit() and pid != "0":
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _start_proc(svc: dict) -> subprocess.Popen:
    """Spawn a service, redirect output to its log file."""
    log_file = open(_log_path(svc["name"]), "a", encoding="utf-8", buffering=1)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.Popen(
        svc["cmd"],
        cwd=svc["cwd"],
        stdout=log_file,
        stderr=log_file,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,  # no terminal window on Windows
    )
    return proc


# ── Start / stop ───────────────────────────────────────────────────────────────

def start_service(svc: dict, wait: bool = True):
    name = svc["name"]
    st   = _state[name]

    # clear port if occupied
    if svc.get("port"):
        _kill_port(svc["port"])

    log.info("Starting %-18s ...", name)
    st["status"] = "starting"

    try:
        proc = _start_proc(svc)
    except FileNotFoundError as e:
        log.error("%-18s  FAILED to start: %s", name, e)
        st["status"] = "stopped"
        return

    _procs[name] = proc
    st["pid"]    = proc.pid

    if not wait:
        st["status"] = "running"
        return

    # wait for health check
    deadline = time.time() + svc["timeout"]
    while time.time() < deadline:
        if proc.poll() is not None:
            log.error("%-18s  exited during startup (code %s) — see logs/%s.log",
                      name, proc.returncode, name)
            st["status"] = "stopped"
            return
        if _is_healthy(svc):
            st["status"]       = "running"
            st["last_healthy"] = time.time()
            log.info("%-18s  UP  (pid=%d)", name, proc.pid)
            return
        time.sleep(1)

    # timed out — still mark running if process is alive
    if proc.poll() is None:
        log.warning("%-18s  health check timed out but process alive — continuing", name)
        st["status"] = "degraded"
    else:
        log.error("%-18s  failed to start within %ds", name, svc["timeout"])
        st["status"] = "stopped"


def stop_all():
    log.info("Stopping all services...")
    for svc in reversed(SERVICES):
        name = svc["name"]
        proc = _procs.get(name)
        if proc and proc.poll() is None:
            log.info("  Stopping %s (pid=%d)", name, proc.pid)
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        if svc.get("port"):
            _kill_port(svc["port"])
        _state[name]["status"] = "stopped"
        _state[name]["pid"]    = None
    log.info("All stopped.")


# ── Monitor thread ─────────────────────────────────────────────────────────────

def _monitor():
    BACKOFF = [5, 10, 20, 40, 60]   # seconds between restart attempts

    while not _stop_event.wait(10):  # check every 10 seconds
        for svc in SERVICES:
            name = svc["name"]
            st   = _state[name]

            if st["status"] in ("stopped", "starting", "restarting"):
                continue
            if not svc.get("restart"):
                continue

            proc = _procs.get(name)
            dead = (proc is None or proc.poll() is not None)

            if dead:
                since = time.time() - st["last_restart"]
                idx   = min(st["restarts"], len(BACKOFF) - 1)
                wait  = BACKOFF[idx]
                if since < wait:
                    continue
                log.warning("%-18s  died — restarting (attempt %d, waited %ds)",
                            name, st["restarts"] + 1, wait)
                st["status"]       = "restarting"
                st["restarts"]    += 1
                st["last_restart"] = time.time()
                threading.Thread(target=start_service, args=(svc,), daemon=True).start()
                continue

            # process alive — run health check
            if _is_healthy(svc):
                st["status"]       = "running"
                st["last_healthy"] = time.time()
            else:
                age = time.time() - st["last_healthy"]
                if age > 30:
                    st["status"] = "degraded"


# ── Status HTTP server ─────────────────────────────────────────────────────────

class _StatusHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):  # silence request logs
        pass

    def do_GET(self):
        if self.path not in ("/status", "/status/"):
            self.send_response(404)
            self.end_headers()
            return
        payload = json.dumps({
            "services": {
                name: {
                    "status":    st["status"],
                    "pid":       st["pid"],
                    "restarts":  st["restarts"],
                }
                for name, st in _state.items()
            },
            "all_ok": all(st["status"] == "running" for st in _state.values()),
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)


def _run_status_server():
    srv = HTTPServer(("127.0.0.1", STATUS_PORT), _StatusHandler)
    while not _stop_event.is_set():
        srv.handle_request()


# ── Main ───────────────────────────────────────────────────────────────────────

def _ensure_mongo_data():
    (ROOT / "mongo-data").mkdir(exist_ok=True)


def run():
    _ensure_mongo_data()

    # Status API thread (widget polls this)
    threading.Thread(target=_run_status_server, daemon=True).start()
    log.info("Status API: http://localhost:%d/status", STATUS_PORT)

    # Start services in order, each waiting for health before next
    for svc in SERVICES:
        if _stop_event.is_set():
            break
        start_service(svc, wait=True)

    log.info("All services started. Monitoring...")

    # Monitor thread for auto-restart
    threading.Thread(target=_monitor, daemon=True).start()

    # Handle Ctrl-C / SIGTERM
    def _handle_shutdown(*_):
        log.info("Shutdown signal received.")
        _stop_event.set()
        stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    # Block main thread
    while not _stop_event.is_set():
        time.sleep(1)


def cmd_stop():
    """Send stop signal by killing all ports."""
    print("Stopping all services...")
    for svc in SERVICES:
        if svc.get("port"):
            _kill_port(svc["port"])
            print(f"  Killed port {svc['port']}")
    print("Done.")


def cmd_status():
    """Print current status from the running supervisor."""
    try:
        with urllib.request.urlopen(f"http://localhost:{STATUS_PORT}/status", timeout=3) as r:
            data = json.loads(r.read())
        print(f"\n{'SERVICE':<20}  {'STATUS':<12}  {'PID':<8}  RESTARTS")
        print("-" * 52)
        for name, info in data["services"].items():
            print(f"{name:<20}  {info['status']:<12}  {str(info['pid'] or ''):<8}  {info['restarts']}")
        print()
        print("Overall:", "OK" if data["all_ok"] else "DEGRADED")
    except Exception as e:
        print(f"Supervisor not running (can't reach port {STATUS_PORT}): {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stop",   action="store_true", help="kill all services")
    ap.add_argument("--status", action="store_true", help="print status")
    args = ap.parse_args()

    if args.stop:
        cmd_stop()
    elif args.status:
        cmd_status()
    else:
        run()
