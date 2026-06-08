"""
Honcho API — SAGE/KAIROS Dashboard WebSocket & REST Endpoints
=============================================================
Provides the data layer for the Honcho dashboard components:

  MetaLearningViz  — real-time meta-agent rule rewrite events
  KAIROS Score Viz — live KAIROS phase scores
  SwarmNexus       — active agents and inter-agent comms
  SovereignPanel   — hardware utilisation (CPU/GPU/NPU/RAM)

FastAPI routes:
  GET  /honcho/status          — full system status
  GET  /honcho/sage/status     — SAGE loop status + next schedule
  GET  /honcho/sage/history    — last 20 SAGE cycle reports
  POST /honcho/sage/run        — trigger a manual SAGE cycle
  GET  /honcho/kairos/plans    — recent KAIROS plans
  GET  /honcho/memory/stats    — GhostRecall + Iron Dome + Triage stats
  GET  /honcho/meta/history    — Meta-Agent rewrite history
  GET  /honcho/gitops/recent   — recent Git-Ops mutations
  GET  /honcho/ibac/log        — recent IBAC events
  GET  /honcho/hardware        — CPU/GPU/RAM utilisation (psutil)
  WS   /honcho/ws              — real-time event stream (all SAGE events)

Usage:
    from kairos.honcho_api import honcho_router
    app.include_router(honcho_router, prefix="/honcho")
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

LOG = logging.getLogger("aethyro.honcho")

honcho_router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_import_sage():
    try:
        from .sage_loop import SAGELoop
        return SAGELoop.instance()
    except Exception as e:
        LOG.debug("SAGE not available: %s", e)
        return None


def _safe_import_meta():
    try:
        from .meta_agent import MetaAgent
        return MetaAgent.instance()
    except Exception as e:
        LOG.debug("MetaAgent not available: %s", e)
        return None


def _safe_import_memory():
    try:
        from memory.ghostrecall import ghost
        from memory.iron_dome import IronDome
        from memory.triage_governor import governor
        return ghost, IronDome.instance(), governor
    except Exception as e:
        LOG.debug("Memory not available: %s", e)
        return None, None, None


def _safe_import_gitops():
    try:
        from .gitops_mutator import GitOpsMutator
        return GitOpsMutator.instance()
    except Exception as e:
        LOG.debug("GitOps not available: %s", e)
        return None


def _safe_import_verifier():
    try:
        from .verification import VerificationPipeline
        return VerificationPipeline.instance()
    except Exception as e:
        LOG.debug("Verifier not available: %s", e)
        return None


def _hardware_stats() -> Dict:
    """Collect real-time hardware utilisation via psutil."""
    try:
        cpu_pct   = psutil.cpu_percent(interval=0.2)
        ram       = psutil.virtual_memory()
        ram_pct   = ram.percent
        ram_gb    = round(ram.used / 1e9, 2)
        ram_total = round(ram.total / 1e9, 2)

        # GPU stats via nvidia-smi (if available)
        gpu = {}
        try:
            import subprocess
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3,
            )
            if out.returncode == 0:
                parts = out.stdout.strip().split(", ")
                if len(parts) >= 4:
                    gpu = {
                        "utilization_pct": int(parts[0]),
                        "vram_used_mb":    int(parts[1]),
                        "vram_total_mb":   int(parts[2]),
                        "temperature_c":   int(parts[3]),
                        "vram_pct":        round(int(parts[1]) / max(1, int(parts[2])) * 100, 1),
                    }
        except Exception:
            pass

        # Disk
        disk = psutil.disk_usage("C:\\")
        disk_gb = round(disk.used / 1e9, 2)
        disk_total = round(disk.total / 1e9, 2)

        return {
            "cpu_pct":    cpu_pct,
            "ram_pct":    ram_pct,
            "ram_gb":     ram_gb,
            "ram_total_gb": ram_total,
            "gpu":        gpu,
            "disk_used_gb": disk_gb,
            "disk_total_gb": disk_total,
            "disk_pct":   round(disk.percent, 1),
            "ts":         time.time(),
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# REST endpoints
# ─────────────────────────────────────────────────────────────────────────────

@honcho_router.get("/status")
async def honcho_status():
    """Full system status for the Honcho dashboard."""
    sage     = _safe_import_sage()
    meta     = _safe_import_meta()
    ghost, dome, triage = _safe_import_memory()
    gitops   = _safe_import_gitops()
    verifier = _safe_import_verifier()

    status = {
        "system":  "Aethyro KAIROS/SAGE Engine",
        "ts":      time.time(),
        "sage":    sage.status() if sage else {"error": "not loaded"},
        "meta":    meta.stats() if meta else {"error": "not loaded"},
        "memory": {
            "ghostrecall": ghost.stats() if ghost else {"error": "not loaded"},
            "iron_dome":   dome.stats() if dome else {"error": "not loaded"},
            "triage":      triage.stats() if triage else {"error": "not loaded"},
        },
        "gitops":    gitops.stats() if gitops else {"error": "not loaded"},
        "verifier":  verifier.stats() if verifier else {"error": "not loaded"},
        "hardware":  _hardware_stats(),
    }
    return status


@honcho_router.get("/sage/status")
async def sage_status():
    sage = _safe_import_sage()
    if not sage:
        return {"error": "SAGE not loaded"}
    return sage.status()


@honcho_router.get("/sage/history")
async def sage_history(limit: int = 20):
    sage = _safe_import_sage()
    if not sage:
        return {"history": []}
    return {"history": sage.history(limit=limit)}


class ManualRunRequest(BaseModel):
    goal: Optional[str] = None
    cycles: int = 1


@honcho_router.post("/sage/run")
async def sage_run(req: ManualRunRequest, background_tasks: BackgroundTasks):
    """Trigger a manual SAGE cycle (runs in background)."""
    sage = _safe_import_sage()
    if not sage:
        return {"error": "SAGE not loaded"}
    if sage._running or sage._cycle_running:
        return {"error": "SAGE is already running", "cycle": sage._cycle_number}

    # Claim the slot SYNCHRONOUSLY before scheduling the background task.
    # Without this, two concurrent POST /sage/run requests both pass the guard
    # above (asyncio is single-threaded but both requests are handled before
    # either background task starts), spawning two concurrent SAGE cycles.
    sage._cycle_running = True

    goal = req.goal or f"Manual SAGE trigger - {time.strftime('%Y-%m-%d %H:%M')}"

    async def _run():
        try:
            if req.cycles == 1:
                await sage.run_cycle(goal=goal)
            else:
                await sage.run_session(cycles=min(req.cycles, CYCLES_PER_SESSION))
        except Exception as exc:
            LOG.error("[SAGE] Background run error: %s", exc, exc_info=True)
        finally:
            # Belt-and-suspenders: run_cycle/run_session clear their own flags
            # via try/finally, but clear here too in case something weird happens
            sage._cycle_running = False

    background_tasks.add_task(_run)
    return {
        "status":  "started",
        "goal":    goal,
        "cycles":  req.cycles,
        "cycle_n": sage._cycle_number + 1,
    }


@honcho_router.get("/kairos/plans")
async def kairos_plans(limit: int = 20):
    try:
        from .kairos import KAIROSEngine
        plans = KAIROSEngine.load_plans(limit=limit)
        return {"plans": plans}
    except Exception as e:
        return {"error": str(e)}


@honcho_router.get("/memory/stats")
async def memory_stats():
    ghost, dome, triage = _safe_import_memory()
    return {
        "ghostrecall": ghost.stats() if ghost else {},
        "iron_dome":   dome.stats() if dome else {},
        "triage":      triage.stats() if triage else {},
    }


@honcho_router.get("/meta/history")
async def meta_history(limit: int = 20):
    meta = _safe_import_meta()
    if not meta:
        return {"history": []}
    return {
        "history": meta.history(limit=limit),
        "stats":   meta.stats(),
    }


@honcho_router.get("/gitops/recent")
async def gitops_recent(limit: int = 20):
    gitops = _safe_import_gitops()
    if not gitops:
        return {"mutations": []}
    return {
        "mutations": gitops.recent_mutations(limit=limit),
        "stats":     gitops.stats(),
    }


@honcho_router.get("/ibac/log")
async def ibac_log_redirect(limit: int = 50):
    """Proxy to IBAC log endpoint."""
    from pathlib import Path
    import json
    log_path = Path(__file__).parent / "data" / "ibac_events.jsonl"
    if not log_path.exists():
        return {"events": []}
    lines = log_path.read_text().strip().splitlines()
    events = []
    for line in reversed(lines[-limit:]):
        try:
            events.append(json.loads(line))
        except Exception:
            pass
    return {"events": events, "total": len(lines)}


@honcho_router.get("/hardware")
async def hardware_stats():
    return _hardware_stats()


@honcho_router.get("/iron_dome/verify")
async def iron_dome_verify():
    _, dome, _ = _safe_import_memory()
    if not dome:
        return {"error": "Iron Dome not loaded"}
    valid, errors = dome.verify_chain()
    return {"valid": valid, "errors": errors[:10], "total_errors": len(errors)}


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket — real-time SAGE event stream
# ─────────────────────────────────────────────────────────────────────────────

@honcho_router.websocket("/ws")
async def honcho_ws(websocket: WebSocket):
    """
    WebSocket endpoint for real-time SAGE events.
    Clients receive JSON events as they happen:
      - cycle_start, cycle_complete
      - step (state_assessment, strategic_mapping, proposal_generation, ...)
      - proposal_scored, deployed
      - meta_rewrite
      - session_start, session_complete
      - scheduled
    Also sends hardware ping every 5s.
    """
    await websocket.accept()
    LOG.info("[Honcho WS] Client connected from %s", websocket.client)

    sage = _safe_import_sage()
    if not sage:
        await websocket.send_json({"event": "error", "msg": "SAGE not loaded"})
        await websocket.close()
        return

    q = sage.add_ws_client()

    # Send current status immediately on connect
    try:
        await websocket.send_json({"event": "connected", "status": sage.status(), "ts": time.time()})
    except Exception:
        pass

    # Background hardware ping task
    async def _hw_ping():
        while True:
            await asyncio.sleep(5)
            try:
                await websocket.send_json({"event": "hardware", "data": _hardware_stats()})
            except Exception:
                break

    hw_task = asyncio.create_task(_hw_ping())

    try:
        while True:
            # Forward SAGE events from queue
            try:
                payload = await asyncio.wait_for(q.get(), timeout=1.0)
                await websocket.send_text(payload)
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({"event": "ping", "ts": time.time()})
                except Exception:
                    break
            except asyncio.QueueEmpty:
                pass
    except WebSocketDisconnect:
        LOG.info("[Honcho WS] Client disconnected")
    except Exception as e:
        LOG.warning("[Honcho WS] Error: %s", e)
    finally:
        hw_task.cancel()
        sage.remove_ws_client(q)


# Avoid circular import
try:
    from .sage_loop import CYCLES_PER_SESSION
except ImportError:
    CYCLES_PER_SESSION = 10
