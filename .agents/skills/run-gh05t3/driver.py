#!/usr/bin/env python3
"""
GH05T3 Sovereign Stack Driver
================================
Agent-facing harness for the full GH05T3 / Avery AI stack.
Run from the GH05T3 repo root.

Usage:
  python .claude/skills/run-gh05t3/driver.py health
  python .claude/skills/run-gh05t3/driver.py chat "What is the sovereign mission?"
  python .claude/skills/run-gh05t3/driver.py swarm "Review the payments module for security issues"
  python .claude/skills/run-gh05t3/driver.py kairos
  python .claude/skills/run-gh05t3/driver.py memory "sovereign economy"
  python .claude/skills/run-gh05t3/driver.py cascade
  python .claude/skills/run-gh05t3/driver.py train
  python .claude/skills/run-gh05t3/driver.py agents
  python .claude/skills/run-gh05t3/driver.py avery
  python .claude/skills/run-gh05t3/driver.py smoke
"""
from __future__ import annotations

import io
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows (avoids cp1252 encode errors for em-dashes etc.)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Locate repo root ──────────────────────────────────────────────────────────
SCRIPT = Path(__file__).resolve()
REPO_ROOT = SCRIPT.parents[3]   # .claude/skills/run-gh05t3/driver.py → repo root
BACKEND_DIR = REPO_ROOT / "backend"
VENV_PYTHON = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = REPO_ROOT / "venv" / "Scripts" / "python.exe"

# ── Re-exec under the backend venv if needed ─────────────────────────────────
if VENV_PYTHON.exists() and str(VENV_PYTHON) != sys.executable:
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

# ── Now import requests (available in the venv) ───────────────────────────────
try:
    import requests
except ImportError:
    print("[driver] 'requests' not found. Install: pip install requests")
    sys.exit(1)

# ── Load backend .env ─────────────────────────────────────────────────────────
ENV_PATH = BACKEND_DIR / ".env"
_ENV: dict[str, str] = {}
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            _ENV[k.strip()] = v.strip()

API_TOKEN   = _ENV.get("GH05T3_API_TOKEN", "")
GATEWAY_URL = _ENV.get("GATEWAY_URL", "http://localhost:8002")
BACKEND_URL = _ENV.get("INSTANCE_URL", "http://localhost:8001")

_HEADERS = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}

# ── Color helpers ─────────────────────────────────────────────────────────────
G = "\033[92m"   # green
Y = "\033[93m"   # yellow
R = "\033[91m"   # red
B = "\033[94m"   # blue
C = "\033[96m"   # cyan
W = "\033[97m"   # white
DIM = "\033[2m"
RESET = "\033[0m"

def ok(s):  return f"{G}✓{RESET} {s}"
def warn(s): return f"{Y}⚠{RESET} {s}"
def err(s):  return f"{R}✗{RESET} {s}"
def hdr(s):  return f"\n{B}{'─'*60}{RESET}\n{W}{s}{RESET}\n{B}{'─'*60}{RESET}"


# ── TCP probe (detects zombie-listen vs healthy vs dead) ──────────────────────

def tcp_probe(host: str, port: int, timeout: float = 1.0) -> str:
    """
    Returns: 'open' | 'refused' | 'timeout' | 'error'

    Zombie-listen is port in LISTENING state (netstat) but refusing connections.
    Open means OS handshake completed — server is actually accepting.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return "open"
    except ConnectionRefusedError:
        return "refused"
    except socket.timeout:
        return "timeout"
    except Exception:
        return "error"


# ── HTTP health probe ─────────────────────────────────────────────────────────

def http_get(url: str, timeout: float = 5.0) -> tuple[int | None, dict | str | None]:
    try:
        r = requests.get(url, headers=_HEADERS, timeout=timeout)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text
    except requests.exceptions.ConnectionError as e:
        return None, f"ConnectionError: {e}"
    except requests.exceptions.Timeout:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)


def http_post(url: str, body: dict, timeout: float = 30.0) -> tuple[int | None, dict | str | None]:
    try:
        r = requests.post(url, json=body, headers=_HEADERS, timeout=timeout)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text
    except requests.exceptions.ConnectionError as e:
        return None, f"ConnectionError: {e}"
    except requests.exceptions.Timeout:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)


# ─────────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────────

def cmd_health(_args: list[str]) -> None:
    """Full service topology health check."""
    print(hdr("GH05T3 SOVEREIGN STACK — HEALTH MAP"))

    services = [
        ("MongoDB",          "localhost", 27017, None,                      None),
        ("backend (economy)","localhost", 8001,  f"{BACKEND_URL}/api/health", 8.0),
        ("gateway_v3 (swarm)","localhost", 8002, f"{GATEWAY_URL}/health",    5.0),
        ("frontend",         "localhost", 3210,  None,                      None),
        ("gh05t3-inference", "localhost", 8010,  "http://localhost:8010/health", 3.0),
        ("llama verifier",   "localhost", 8011,  "http://localhost:8011/health", 3.0),
        ("llama CPU",        "localhost", 8012,  "http://localhost:8012/health", 3.0),
        ("Ollama",           "localhost", 11434, "http://localhost:11434/api/version", 3.0),
        ("Qdrant",           "localhost", 6333,  "http://localhost:6333/health", 2.0),
    ]

    for name, host, port, health_url, http_timeout in services:
        tcp = tcp_probe(host, port)

        if tcp == "open":
            if health_url:
                code, body = http_get(health_url, timeout=http_timeout)
                if code == 200:
                    detail = ""
                    if isinstance(body, dict):
                        detail = body.get("status") or body.get("version") or json.dumps(body)[:60]
                    status = ok(f"{name:<24} :{port}  HTTP {code}  {DIM}{detail}{RESET}")
                elif code is None:
                    status = warn(f"{name:<24} :{port}  TCP open, HTTP timeout — event loop likely blocked")
                else:
                    status = warn(f"{name:<24} :{port}  HTTP {code}")
            else:
                status = ok(f"{name:<24} :{port}  TCP open")

        elif tcp == "refused":
            # Check if netstat shows LISTENING (zombie-listen state)
            try:
                ns = subprocess.check_output(
                    ["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL, timeout=3
                )
                listening = f":{port} " in ns and "LISTENING" in ns
            except Exception:
                listening = False

            if listening:
                status = warn(f"{name:<24} :{port}  ZOMBIE — netstat LISTENING but TCP refuses. Restart required.")
            else:
                status = err(f"{name:<24} :{port}  Down")

        elif tcp == "timeout":
            status = warn(f"{name:<24} :{port}  TCP timeout (firewall?)")
        else:
            status = err(f"{name:<24} :{port}  Down")

        print(f"  {status}")

    # LLM provider config
    print()
    provider = _ENV.get("LLM_PROVIDER", "?")
    model    = _ENV.get("LLM_MODEL", "?")
    cost_free = _ENV.get("COST_FREE_ONLY", "0")
    enable_ops = _ENV.get("ENABLE_OPS", "0")
    print(f"  {C}LLM{RESET}  provider={provider}  model={model}  cost_free_only={cost_free}")
    print(f"  {C}OPS{RESET}  ENABLE_OPS={enable_ops}  (herald + cmd_listener)")
    print(f"  {C}ENV{RESET}  .env loaded from {ENV_PATH}")


def cmd_chat(args: list[str]) -> None:
    """Send a chat message to Avery via backend."""
    msg = " ".join(args) if args else "Hello Avery. Give me a status update on the sovereign economy."
    print(hdr(f"AVERY CHAT"))
    print(f"  {DIM}→ {msg}{RESET}\n")

    # Try gateway first (richer Avery persona), fall back to backend
    for label, url in [("gateway", f"{GATEWAY_URL}/chat"), ("backend", f"{BACKEND_URL}/api/chat")]:
        tcp_port = 8002 if "8002" in url else 8001
        if tcp_probe("localhost", tcp_port) != "open":
            print(f"  {warn(f'{label} unreachable — skipping')}")
            continue

        code, body = http_post(url, {"message": msg}, timeout=60.0)
        if code == 200 and isinstance(body, dict):
            reply = body.get("reply") or body.get("response") or body.get("message") or str(body)
            agent = body.get("agent", label)
            model = body.get("model", "")
            print(f"  {G}{agent}{RESET}  {DIM}[via {label}  model={model}]{RESET}\n")
            print(f"  {reply}\n")
            return
        else:
            print(f"  {warn(f'{label}: HTTP {code} — {str(body)[:120]}')}")

    print(f"  {err('No live service could handle the chat. Run run.bat to start the stack.')}")


def cmd_swarm(args: list[str]) -> None:
    """Delegate a task to the specialist swarm agents."""
    task = " ".join(args) if args else "Summarize the current state of the sovereign economy stack."
    print(hdr("SWARM DELEGATION"))
    print(f"  {DIM}task → {task}{RESET}\n")

    if tcp_probe("localhost", 8002) != "open":
        print(f"  {err('Gateway (8002) unreachable. Cannot reach swarm.')}")
        return

    code, body = http_post(
        f"{GATEWAY_URL}/swarm/delegate",
        {"task": task, "priority": "high"},
        timeout=120.0,
    )
    if code == 200 and isinstance(body, dict):
        results = body.get("results", [body])
        for item in (results if isinstance(results, list) else [results]):
            agent = item.get("agent", "UNKNOWN")
            content = item.get("content") or item.get("result") or str(item)
            print(f"  {C}[{agent}]{RESET}  {content}\n")
    else:
        print(f"  {err(f'HTTP {code}: {str(body)[:200]}')}")


def cmd_agents(_args: list[str]) -> None:
    """List all swarm agents with live stats."""
    print(hdr("SWARM AGENT REGISTRY"))

    if tcp_probe("localhost", 8002) != "open":
        print(f"  {err('Gateway (8002) unreachable.')}")
        return

    code, body = http_get(f"{GATEWAY_URL}/swarm/agents", timeout=5.0)
    if code == 200 and isinstance(body, dict):
        agents = body.get("agents", body)
        if isinstance(agents, list):
            for a in agents:
                aid    = a.get("id",       a.get("agent_id", "?"))
                status = a.get("status",   "?")
                msgs   = a.get("messages", 0)
                last   = a.get("last_msg", "—")[:60]
                color  = G if status == "online" else Y
                print(f"  {color}{aid:<12}{RESET} status={status}  msgs={msgs}  last={DIM}{last}{RESET}")
        else:
            print(json.dumps(agents, indent=2)[:800])
    else:
        print(f"  {err(f'HTTP {code}: {str(body)[:200]}')}")


def cmd_avery(_args: list[str]) -> None:
    """Show Avery's public identity card and team roster."""
    print(hdr("AVERY — SOVEREIGN AI"))

    if tcp_probe("localhost", 8002) != "open":
        print(f"  {err('Gateway (8002) unreachable.')}")
        return

    code, body = http_get(f"{GATEWAY_URL}/avery", timeout=5.0)
    if code == 200:
        print(json.dumps(body, indent=2)[:1000])
    else:
        print(f"  {err(f'HTTP {code}: {str(body)[:200]}')}")

    print()
    code, team = http_get(f"{GATEWAY_URL}/avery/team", timeout=5.0)
    if code == 200:
        agents = team if isinstance(team, list) else team.get("team", [])
        for a in agents:
            name  = a.get("name", a.get("agent_id", "?"))
            title = a.get("title", "")
            bio   = a.get("bio", "")[:80]
            print(f"  {C}{name}{RESET}  {DIM}{title}{RESET}")
            if bio:
                print(f"    {bio}")


def cmd_kairos(_args: list[str]) -> None:
    """Show recent KAIROS evolutionary cycles and elite archive."""
    print(hdr("KAIROS EVOLUTIONARY CYCLES"))

    # Try gateway, then backend
    for label, url in [
        ("gateway", f"{GATEWAY_URL}/kairos/elite"),
        ("backend", f"{BACKEND_URL}/api/kairos/recent"),
    ]:
        port = 8002 if "8002" in url else 8001
        if tcp_probe("localhost", port) != "open":
            continue
        code, body = http_get(url, timeout=8.0)
        if code == 200:
            cycles = body if isinstance(body, list) else body.get("cycles", body.get("recent", []))
            if not cycles:
                print(f"  {warn('No KAIROS cycles recorded yet.')}")
                return
            for c in (cycles[-10:] if isinstance(cycles, list) else []):
                score   = c.get("score",    0.0)
                is_elite = c.get("is_elite", False)
                tag     = c.get("tag",      "—")
                ts      = c.get("timestamp", "")
                proposal = c.get("proposal", c.get("proposal_summary", ""))[:80]
                verdict  = c.get("verdict", "")[:60]
                star    = f"{Y}★{RESET}" if is_elite else " "
                color   = G if score >= 0.9 else (Y if score >= 0.7 else R)
                print(f"  {star} score={color}{score:.2f}{RESET}  {DIM}{tag}{RESET}")
                if proposal:
                    print(f"      {proposal}")
                if verdict:
                    print(f"      {DIM}verdict: {verdict}{RESET}")
            return
        print(f"  {warn(f'{label}: HTTP {code}')}")

    # Fall back: read KAIROS JSONL directly
    kairos_log = BACKEND_DIR / "evolution" / "kairos_log.jsonl"
    if kairos_log.exists():
        lines = kairos_log.read_text(encoding="utf-8").strip().splitlines()
        cycles = [json.loads(l) for l in lines[-10:] if l.strip()]
        if not cycles:
            print(f"  {warn('No KAIROS cycles in log file.')}")
            return
        print(f"  {DIM}(read directly from {kairos_log}){RESET}\n")
        for c in cycles:
            score    = c.get("score", 0.0)
            is_elite = c.get("is_elite", False)
            proposal = str(c.get("proposal", ""))[:80]
            verdict  = str(c.get("verdict", ""))[:60]
            star     = f"{Y}★{RESET}" if is_elite else " "
            color    = G if score >= 0.9 else (Y if score >= 0.7 else R)
            print(f"  {star} score={color}{score:.2f}{RESET}  {proposal}")
            if verdict:
                print(f"      {DIM}{verdict}{RESET}")
    else:
        print(f"  {err('KAIROS log not found and no service reachable.')}")


def cmd_memory(args: list[str]) -> None:
    """Query the memory palace."""
    query = " ".join(args) if args else "sovereign economy"
    print(hdr(f"MEMORY PALACE — query: {query}"))

    for label, url, port in [
        ("gateway",  f"{GATEWAY_URL}/memory/recall",   8002),
        ("backend",  f"{BACKEND_URL}/api/memory/search", 8001),
    ]:
        if tcp_probe("localhost", port) != "open":
            continue
        payload = {"query": query, "limit": 5} if "recall" in url else {"q": query, "limit": 5}
        code, body = http_post(url, payload, timeout=10.0) if "recall" in url else (
            *[None, None],
        )
        # backend search is GET
        if "search" in url:
            code, body = http_get(f"{BACKEND_URL}/api/memory/search?q={requests.utils.quote(query)}&limit=5", timeout=8.0)

        if code == 200 and isinstance(body, dict):
            shards = body.get("shards") or body.get("results") or body.get("memories") or []
            if not shards:
                print(f"  {warn('No memory shards found for that query.')}")
                return
            for s in shards:
                content = s.get("content") or s.get("text") or str(s)
                score   = s.get("score", s.get("relevance", ""))
                ts      = s.get("timestamp", s.get("created_at", ""))
                print(f"  {C}[{score}]{RESET}  {content[:120]}")
                if ts:
                    print(f"  {DIM}  {ts}{RESET}")
            return
        if code is not None:
            print(f"  {warn(f'{label}: HTTP {code}: {str(body)[:100]}')}")

    # Direct SQLite fallback
    db_path = Path(_ENV.get("MEMORY_DB_PATH", str(BACKEND_DIR / "memory" / "palace.db")))
    if db_path.exists():
        import sqlite3
        try:
            conn = sqlite3.connect(str(db_path))
            rows = conn.execute(
                "SELECT content, room, timestamp FROM shards WHERE content LIKE ? ORDER BY timestamp DESC LIMIT 5",
                (f"%{query}%",),
            ).fetchall()
            conn.close()
            if rows:
                print(f"  {DIM}(SQLite fallback — {db_path}){RESET}\n")
                for content, room, ts in rows:
                    print(f"  {C}[{room}]{RESET}  {str(content)[:120]}")
                    print(f"  {DIM}  {ts}{RESET}")
            else:
                print(f"  {warn(f'No results in SQLite for: {query}')}")
        except Exception as e:
            print(f"  {err(f'SQLite error: {e}')}")
    else:
        print(f"  {err('No service reachable and no SQLite DB found.')}")


def cmd_cascade(_args: list[str]) -> None:
    """Test the full LLM cascade chain: gh05t3 → Ollama → Groq → Gemini → Anthropic."""
    print(hdr("LLM CASCADE CHAIN TEST"))

    providers = [
        ("gh05t3-inference", "localhost", 8010, "http://localhost:8010/v1/chat/completions",
         {"model": "default", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5}),
        ("Ollama",           "localhost", 11434, "http://localhost:11434/api/generate",
         {"model": _ENV.get("LLM_MODEL", "qwen2.5:7b"), "prompt": "ping", "stream": False}),
    ]

    for name, host, port, url, payload in providers:
        tcp = tcp_probe(host, port)
        if tcp != "open":
            print(f"  {err(f'{name:<20} :{port}  Down')}")
            continue
        t0 = time.time()
        code, body = http_post(url, payload, timeout=30.0)
        elapsed = time.time() - t0
        if code == 200:
            resp = ""
            if isinstance(body, dict):
                resp = (body.get("response") or
                        (body.get("choices") or [{}])[0].get("message", {}).get("content") or "")
            print(f"  {ok(f'{name:<20} :{port}  {elapsed:.1f}s  {DIM}{str(resp)[:40]}{RESET}')}")
        else:
            print(f"  {warn(f'{name:<20} :{port}  HTTP {code}')}")

    # Check backend's LLM config
    if tcp_probe("localhost", 8001) == "open":
        code, body = http_get(f"{BACKEND_URL}/api/llm/config", timeout=5.0)
        if code == 200:
            print(f"\n  {C}Backend LLM config:{RESET} {json.dumps(body, indent=2)[:300]}")

    # Cascade order from .env
    provider = _ENV.get("LLM_PROVIDER", "ollama")
    model    = _ENV.get("LLM_MODEL", "qwen2.5:7b")
    cost_free = _ENV.get("COST_FREE_ONLY", "0") == "1"
    print(f"\n  {C}Active cascade:{RESET} provider={provider}  model={model}  cost_free_only={cost_free}")
    if cost_free:
        print(f"  {DIM}  Order: gh05t3(8010) → Ollama → Groq → Gemini (Anthropic blocked by COST_FREE_ONLY){RESET}")
    else:
        print(f"  {DIM}  Order: gh05t3(8010) → Ollama → Groq → Gemini → Anthropic{RESET}")


def cmd_train(_args: list[str]) -> None:
    """Show training status and continuous learner state."""
    print(hdr("TRAINING STATUS"))

    # Continuous learner state
    state_file = REPO_ROOT / "data" / "continuous_state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            domains = [
                "business", "sales", "product_strategy", "growth", "cfo",
                "content", "legal_ip", "ops", "ml_engineer", "frontier", "core",
            ]
            idx     = state.get("domain_index", 0)
            current = domains[idx % len(domains)] if domains else "?"
            total   = state.get("total_cycles", 0)
            spin    = state.get("spin_pairs", 0)
            uploads = state.get("total_uploads", 0)
            last_err = state.get("last_error", "")
            print(f"  {C}Continuous Learner:{RESET}")
            print(f"    domain={current} ({idx}/{len(domains)})  cycles={total}  spin_pairs={spin}  uploads={uploads}")
            if last_err:
                print(f"    {warn(f'last_error: {last_err[:80]}')}")
        except Exception as e:
            print(f"  {warn(f'Could not read state: {e}')}")
    else:
        print(f"  {DIM}data/continuous_state.json not found (learner not started){RESET}")

    # SPIN dataset size
    spin_file = REPO_ROOT / "data" / "spin_dataset.jsonl"
    if spin_file.exists():
        lines = sum(1 for _ in spin_file.open(encoding="utf-8", errors="ignore"))
        print(f"\n  {C}SPIN dataset:{RESET} {spin_file}  ({lines} pairs)")

    # LoRA adapter
    adapter_dir = BACKEND_DIR / "models" / "gh05t3_lora_adapter"
    if adapter_dir.exists():
        files = list(adapter_dir.iterdir())
        size_mb = sum(f.stat().st_size for f in files if f.is_file()) / 1e6
        print(f"\n  {C}LoRA adapter:{RESET} {adapter_dir}  ({len(files)} files, {size_mb:.1f} MB)")
    else:
        print(f"\n  {warn('LoRA adapter not found — run native\\windows\\train.bat to train')}")

    # Training config
    base_model = _ENV.get("FINETUNE_BASE_MODEL", "?")
    steps      = _ENV.get("FINETUNE_MAX_STEPS",  "?")
    lora_rank  = _ENV.get("FINETUNE_LORA_RANK",  "?")
    print(f"\n  {C}Training config:{RESET} base={base_model}  max_steps={steps}  lora_rank={lora_rank}")
    print(f"  {DIM}  Launcher: native\\windows\\train.bat  →  backend\\training\\train_local.py{RESET}")
    print(f"  {DIM}  Output:   backend\\models\\gh05t3_lora_adapter\\{RESET}")
    print(f"  {DIM}  RunPod:   HF → tastytator/sovereign-economy  (SPIN pairs){RESET}")


def cmd_smoke(_args: list[str]) -> None:
    """Full integration smoke test — every layer, every path."""
    print(hdr("GH05T3 SMOKE TEST — FULL STACK"))
    passed = 0
    failed = 0
    warned = 0

    def check(name: str, result: bool | None, detail: str = ""):
        nonlocal passed, failed, warned
        if result is True:
            print(f"  {ok(name)}  {DIM}{detail}{RESET}")
            passed += 1
        elif result is False:
            print(f"  {err(name)}  {DIM}{detail}{RESET}")
            failed += 1
        else:
            print(f"  {warn(name)}  {DIM}{detail}{RESET}")
            warned += 1

    # TCP layer
    check("MongoDB TCP :27017",      tcp_probe("localhost", 27017) == "open")
    check("backend TCP :8001",       tcp_probe("localhost", 8001)  == "open")
    gw_tcp = tcp_probe("localhost", 8002)
    _gw_detail = ""
    if gw_tcp in ("refused", "timeout"):
        try:
            ns = subprocess.check_output(["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL, timeout=3)
            if ":8002 " in ns and "LISTENING" in ns:
                _gw_detail = "ZOMBIE-LISTEN — netstat shows LISTENING but TCP fails. Restart run.bat."
        except Exception:
            pass
    check("gateway TCP :8002", gw_tcp == "open", _gw_detail)
    check("frontend TCP :3210",      tcp_probe("localhost", 3210)  == "open")
    check("Ollama TCP :11434",       tcp_probe("localhost", 11434) == "open")

    # HTTP layer (skip backend health — event loop frequently blocked)
    code, _ = http_get(f"{BACKEND_URL}/api/state", timeout=12.0)
    check("backend /api/state",      code == 200, f"HTTP {code}")

    if gw_tcp == "open":
        code, body = http_get(f"{GATEWAY_URL}/health", timeout=5.0)
        check("gateway /health",     code == 200, f"HTTP {code}  {str(body)[:60]}")

        code, body = http_get(f"{GATEWAY_URL}/avery", timeout=5.0)
        check("gateway /avery",      code == 200, str(body)[:60] if code == 200 else "")

        code, body = http_get(f"{GATEWAY_URL}/swarm/agents", timeout=5.0)
        n = len(body.get("agents", [])) if isinstance(body, dict) else "?"
        check("gateway /swarm/agents", code == 200, f"{n} agents")

        code, body = http_get(f"{GATEWAY_URL}/mcp/info", timeout=5.0)
        check("gateway MCP /mcp/info", code == 200, str(body)[:60] if code == 200 else "disabled")

    # LLM inference
    ollama_up = tcp_probe("localhost", 11434) == "open"
    if ollama_up:
        code, body = http_get("http://localhost:11434/api/version", timeout=3.0)
        check("Ollama /api/version",  code == 200, str(body)[:40] if code == 200 else "")
        model = _ENV.get("LLM_MODEL", "qwen2.5:7b")
        code2, mlist = http_get("http://localhost:11434/api/tags", timeout=3.0)
        models = [m["name"] for m in (mlist.get("models") or [] if isinstance(mlist, dict) else [])]
        check(f"Ollama model '{model}'", model in models or any(model.split(":")[0] in m for m in models),
              f"available: {', '.join(models[:5])}")

    # Memory palace
    db_path = Path(_ENV.get("MEMORY_DB_PATH", str(BACKEND_DIR / "memory" / "palace.db")))
    check("Memory palace (SQLite)", db_path.exists(), str(db_path))

    # KAIROS log
    kairos_log = BACKEND_DIR / "evolution" / "kairos_log.jsonl"
    if kairos_log.exists():
        n_cycles = sum(1 for _ in kairos_log.open(encoding="utf-8", errors="ignore") if _.strip())
        check("KAIROS log", True, f"{n_cycles} cycles in {kairos_log}")
    else:
        check("KAIROS log", None, "not found — no training cycles run yet")

    # LoRA adapter
    adapter = BACKEND_DIR / "models" / "gh05t3_lora_adapter"
    check("LoRA adapter", adapter.exists(), str(adapter) if adapter.exists() else "run train.bat")

    print()
    color = G if failed == 0 else R
    print(f"  {color}{'─'*50}{RESET}")
    print(f"  {G if failed==0 else R}Passed: {passed}   Failed: {failed}   Warned: {warned}{RESET}")
    if failed > 0:
        print(f"\n  {Y}Run 'run.bat' from the repo root to start all services.{RESET}")
    print()


# ─────────────────────────────────────────────
# DISPATCH
# ─────────────────────────────────────────────

def cmd_stop(args: list[str]) -> None:
    """Stop all GH05T3 services via stop-gh05t3.ps1."""
    print(hdr("GH05T3 STOP"))
    stop_script = REPO_ROOT / "stop-gh05t3.ps1"
    if not stop_script.exists():
        print(f"  {err(f'stop-gh05t3.ps1 not found at {stop_script}')}")
        return
    flag = ["-All"] if "-all" in [a.lower() for a in args] else []
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(stop_script)] + flag,
        capture_output=True, text=True, timeout=20,
    )
    print(result.stdout or "(no output)")
    if result.returncode != 0:
        print(f"  {warn(f'exit code {result.returncode}')}")
        if result.stderr:
            print(f"  {result.stderr[:200]}")


COMMANDS = {
    "health":  (cmd_health,  "Full service topology health check"),
    "chat":    (cmd_chat,    "Chat with Avery  — chat <message>"),
    "swarm":   (cmd_swarm,   "Delegate to swarm agents  — swarm <task>"),
    "agents":  (cmd_agents,  "List swarm agents with live stats"),
    "avery":   (cmd_avery,   "Avery identity card + team roster"),
    "kairos":  (cmd_kairos,  "Recent KAIROS evolutionary cycles"),
    "memory":  (cmd_memory,  "Query memory palace  — memory <search terms>"),
    "cascade": (cmd_cascade, "Test full LLM cascade chain"),
    "stop":    (cmd_stop,    "Stop all GH05T3 services  — stop [-all kills learner/amplifier too]"),
    "train":   (cmd_train,   "Training + continuous learner state"),
    "smoke":   (cmd_smoke,   "Full integration smoke test"),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(f"\n{W}GH05T3 Sovereign Stack Driver{RESET}\n")
        print(f"  Run from:  {REPO_ROOT}\n")
        for name, (_, desc) in COMMANDS.items():
            print(f"  {C}{name:<10}{RESET} {desc}")
        print()
        print(f"  {DIM}Example: python .claude/skills/run-gh05t3/driver.py health{RESET}\n")
        return

    cmd = sys.argv[1].lower()
    args = sys.argv[2:]

    fn, _ = COMMANDS.get(cmd, (None, None))
    if fn is None:
        print(f"  {err(f'Unknown command: {cmd}')}")
        print(f"  Available: {', '.join(COMMANDS)}")
        sys.exit(1)

    fn(args)


if __name__ == "__main__":
    main()
