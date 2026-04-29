"""
GH05T3 — GATEWAY v3 (Extended)
================================
Drop-in replacement for integrations/api_server.py.
Extends the original with:
  • WebSocket /ws — streams ALL swarm bus messages live
  • GET /conversations — paginated conversation log
  • GET /conversations/search — full-text search
  • GET /swarm/agents — live agent registry + stats
  • POST /swarm/delegate — delegate task to swarm
  • POST /claude/train — trigger Claude training batch
  • POST /claude/review — Claude architecture review
  • GET /github/status — repo info
  • POST /github/push — push files
  • POST /github/sync-memory — push memory to GitHub
  • WS /ws — unified live event stream (swarm bus relay)
  • All original Omega Loop, KAIROS, Memory, KillSwitch endpoints preserved

Mount at the same port as the original (8000).
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.config import (BACKENDS, GATEWAY_HOST, GATEWAY_PORT,
                          GITHUB_PAT, GITHUB_REPO, GITHUB_BRANCH)
from core.omega_loop import OmegaLoop
from memory.memory_palace import MemoryPalace
from evolution.kairos import KAIROS
from evolution.sage import SAGE
from security.ghost_protocol import GhostProtocol, KillSwitchMode

# v3 additions
from swarm.bus import SwarmBus, SwarmMessage, MsgType
from swarm.agents import GH05T3Swarm
from integrations.claude_integration import ClaudeSwarmAgent
from integrations.github_integration import GitHubAgent, create_github_webhook_router

log = logging.getLogger("gh0st3.gateway_v3")

# ─────────────────────────────────────────────
# SYSTEM INIT
# ─────────────────────────────────────────────

bus     = SwarmBus.instance()
memory  = MemoryPalace()
kairos  = KAIROS()
sage    = SAGE()
omega   = OmegaLoop(memory=memory, kairos=kairos, sage=sage)
ghost   = GhostProtocol()
swarm   = None   # initialized in lifespan
github  = None
claude  = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global swarm, github, claude

    # Boot swarm agents
    swarm  = GH05T3Swarm()
    github = GitHubAgent()
    claude = ClaudeSwarmAgent(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    await swarm.boot_announcement()

    await bus.emit(
        src="GATEWAY",
        content="🖤 GH05T3 v3 GATEWAY ONLINE — Omega Loop + Swarm + Claude + GitHub ACTIVE",
        channel="#broadcast",
        msg_type=MsgType.SYSTEM,
    )

    log.info("GH05T3 v3 gateway online")
    yield

    await swarm.shutdown()
    await github.close()
    await claude.close()
    await omega.close()
    await sage.close()
    log.info("GH05T3 v3 shutdown complete")


app = FastAPI(
    title="GH05T3 v3",
    description="Unified swarm gateway — Omega Loop · SAGE · KAIROS · Claude · GitHub",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount GitHub webhook router
app.include_router(create_github_webhook_router())


# ─────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None
    force_ego: bool = False
    ghost_veil: bool = True

class ChatResponse(BaseModel):
    response: str
    mode: str
    sage_score: float
    sage_verdict: str
    latency_ms: float
    cycle_id: int
    backend_used: str

class KAIROSCycleRequest(BaseModel):
    proposal: str
    verdict: str
    score: float

class RecallRequest(BaseModel):
    query: str
    room: Optional[str] = None
    top_k: int = 5

class KillSwitchRequest(BaseModel):
    mode: str
    key: str

class DelegateRequest(BaseModel):
    task: str
    agent: Optional[str] = None
    metadata: dict = {}

class TrainRequest(BaseModel):
    domain: str = "agent_systems"
    count: int = 5

class ReviewRequest(BaseModel):
    module: str
    source: str = ""

class PushRequest(BaseModel):
    files: dict    # {path: content}
    message: str = "🖤 GH05T3 auto-push"
    branch: str = "main"


# ─────────────────────────────────────────────
# ORIGINAL ROUTES (preserved from v2)
# ─────────────────────────────────────────────

@app.get("/")
async def identity():
    return {
        "name":    "GH05T3",
        "version": "3.0.0",
        "owner":   "leerobber",
        "hardware":"TatorTot — Lenovo LOQ 15AHP10",
        "mesh":    {
            "primary":  "RTX 5050 → vLLM/Qwen2.5-32B-AWQ :8001",
            "verifier": "Radeon 780M → llama.cpp/ROCm :8002",
            "fallback": "Ryzen 7 CPU → llama.cpp :8003",
        },
        "swarm":   [a for a in bus.agents.keys()],
        "kairos_cycles": kairos.stats["total_cycles"],
        "memory_shards": memory.stats()["total_shards"],
        "conv_log":      bus.log.stats["total"],
    }


@app.get("/health")
async def health():
    backend_status = {}
    async with httpx.AsyncClient(timeout=2.0) as client:
        for name, url in BACKENDS.items():
            try:
                resp = await client.get(f"{url}/health", timeout=1.5)
                backend_status[name] = "online" if resp.status_code == 200 else "degraded"
            except Exception:
                backend_status[name] = "offline"
    return {
        "status": "operational" if all(v == "online" for v in backend_status.values()) else "degraded",
        "backends": backend_status,
        "swarm_agents": len(bus.agents),
        "ws_clients": bus.stats["ws_clients"],
        "timestamp": int(time.time()),
    }


@app.get("/status")
async def full_status():
    return {
        "system":    "GH05T3 v3",
        "omega_loop":omega.stats,
        "kairos":    kairos.stats,
        "memory":    memory.stats(),
        "sage":      sage.stats,
        "ghost":     ghost.stats,
        "swarm":     bus.stats,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    trap = await ghost.process_input(req.message)
    if trap is not None:
        return ChatResponse(response=trap, mode="ghost", sage_score=0.0,
                            sage_verdict="TRAPPED", latency_ms=0.0,
                            cycle_id=omega.cycle_count, backend_used="ghost_protocol")

    state = await omega.run(req.message, req.context)

    # Publish to swarm bus for dashboard visibility
    await bus.emit(
        src="USER",
        content=req.message,
        channel="#omega",
        msg_type=MsgType.CHAT,
    )
    await bus.emit(
        src="OMEGA",
        content=state.response,
        channel="#omega",
        msg_type=MsgType.RESULT,
        mode=state.mode.value,
        sage_score=state.sage_score,
        sage_verdict=state.sage_verdict,
        cycle_id=state.cycle_id,
    )

    return ChatResponse(
        response=state.response,
        mode=state.mode.value,
        sage_score=state.sage_score,
        sage_verdict=state.sage_verdict,
        latency_ms=state.latency_ms,
        cycle_id=state.cycle_id,
        backend_used=state.backend_used,
    )


@app.post("/kairos/cycle")
async def record_kairos_cycle(req: KAIROSCycleRequest):
    cycle = kairos.record_cycle(proposal=req.proposal, verdict=req.verdict, score=req.score)
    await bus.emit(
        src="KAIROS",
        content=f"Cycle #{cycle.id} recorded — score={req.score:.2f} verdict={req.verdict}",
        channel="#broadcast",
        msg_type=MsgType.KAIROS,
        cycle_id=cycle.id,
        score=req.score,
        verdict=req.verdict,
        is_elite=cycle.is_elite,
    )
    return cycle.to_dict()


@app.get("/kairos/elite")
async def get_elite_archive():
    return [c.to_dict() for c in kairos.elite_archive]


@app.get("/memory/stats")
async def get_memory_stats():
    return memory.stats()


@app.post("/memory/recall")
async def recall_memory(req: RecallRequest):
    results = await memory.recall(query=req.query, room=req.room, top_k=req.top_k)
    return {"results": results, "count": len(results)}


@app.post("/killswitch")
async def killswitch(req: KillSwitchRequest):
    try:
        mode = KillSwitchMode(req.mode.lower())
    except ValueError:
        raise HTTPException(400, "Invalid mode")
    result = ghost.killswitch.execute(mode=mode, key=req.key)
    if result.get("status") == "denied":
        raise HTTPException(403, "Authentication failed")
    return result


# ─────────────────────────────────────────────
# SWARM ROUTES
# ─────────────────────────────────────────────

@app.get("/swarm/agents")
async def get_agents():
    return {"agents": bus.agents, "stats": swarm.stats if swarm else {}}


@app.post("/swarm/delegate")
async def delegate_task(req: DelegateRequest):
    if not swarm:
        raise HTTPException(503, "Swarm not initialized")
    target = await swarm.delegate(req.task, preferred_agent=req.agent)
    return {"ok": True, "task": req.task, "routed_to": target}


@app.post("/swarm/broadcast")
async def broadcast(content: str, src: str = "API"):
    await bus.emit(src=src, content=content, channel="#broadcast", msg_type=MsgType.CHAT)
    return {"ok": True}


# ─────────────────────────────────────────────
# CONVERSATION LOG ROUTES
# ─────────────────────────────────────────────

@app.get("/conversations")
async def get_conversations(n: int = 100, channel: str = None, src: str = None):
    return {
        "messages": bus.log.recent(n=n, channel=channel, src=src),
        "stats":    bus.log.stats,
    }


@app.get("/conversations/search")
async def search_conversations(q: str, limit: int = 50):
    return {"results": bus.log.search(q, limit=limit)}


@app.get("/conversations/stats")
async def conv_stats():
    return bus.log.stats


# ─────────────────────────────────────────────
# CLAUDE INTEGRATION ROUTES
# ─────────────────────────────────────────────

@app.post("/claude/train")
async def claude_train(req: TrainRequest):
    if not claude:
        raise HTTPException(503, "Claude not initialized")
    scenarios = await claude.trainer.generate_training_batch(req.domain, req.count)
    return {"scenarios": scenarios, "count": len(scenarios), "domain": req.domain}


@app.post("/claude/review")
async def claude_review(req: ReviewRequest):
    if not claude:
        raise HTTPException(503, "Claude not initialized")
    review = await claude.architect.review_module(req.module, req.source)
    return {"review": review, "module": req.module}


@app.post("/claude/upgrade")
async def claude_upgrade(topic: str):
    if not claude:
        raise HTTPException(503, "Claude not initialized")
    proposal = await claude.architect.propose_upgrade(topic)
    return {"proposal": proposal, "topic": topic}


# ─────────────────────────────────────────────
# GITHUB ROUTES
# ─────────────────────────────────────────────

@app.get("/github/status")
async def github_status():
    if not github:
        raise HTTPException(503, "GitHub not initialized")
    try:
        info = await github._gh.repo_info()
        return info
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/github/push")
async def github_push(req: PushRequest):
    if not github:
        raise HTTPException(503, "GitHub not initialized")
    try:
        url = await github._gh.push_files(req.files, req.message, req.branch)
        return {"ok": True, "commit_url": url, "files": len(req.files)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/github/sync-memory")
async def github_sync_memory():
    await bus.emit(
        src="API",
        content="sync memory to github",
        channel="#github",
        msg_type=MsgType.TASK,
    )
    return {"ok": True, "note": "Sync task delegated to GITHUB agent"}


@app.post("/github/commit")
async def github_commit(message: str = "🖤 GH05T3 manual commit"):
    await bus.emit(
        src="API",
        content=f"commit: {message}",
        channel="#github",
        msg_type=MsgType.TASK,
        commit_msg=message,
    )
    return {"ok": True, "message": message}


# ─────────────────────────────────────────────
# WEBSOCKET — LIVE SWARM STREAM
# ─────────────────────────────────────────────

@app.websocket("/ws")
async def ws_stream(ws: WebSocket):
    """
    Real-time swarm bus stream.
    Replays last 50 messages on connect, then streams live.
    """
    await ws.accept()
    q = bus.add_ws_client()

    # Send hello
    await ws.send_text(json.dumps({
        "type": "hello",
        "node": {
            "id":      "GH05T3-TATORTOT",
            "version": "3.0.0",
            "agents":  list(bus.agents.keys()),
        },
        "ts": time.time(),
    }))

    try:
        while True:
            try:
                payload = await asyncio.wait_for(q.get(), timeout=20.0)
                await ws.send_text(payload)
            except asyncio.TimeoutError:
                # Ping
                await ws.send_text(json.dumps({"type": "ping", "ts": time.time()}))
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        bus.remove_ws_client(q)


# ─────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "integrations.gateway_v3:app",
        host=GATEWAY_HOST,
        port=GATEWAY_PORT,
        log_level="info",
        reload=False,
    )
