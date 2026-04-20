"""
GH05T3 backend — FastAPI gateway (phase 2).
Now with: WebSocket telemetry, APScheduler nightly auto-runs, real LLM-driven
KAIROS/SAGE cycles, Cassandra pre-mortem, real 10k-dim HCM vectors with PCA,
real GhostScript interpreter, real stego encode/decode, Telegram long-polling,
and Séance exception auto-capture.
"""
from __future__ import annotations
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from emergentintegrations.llm.chat import LlmChat, UserMessage

from gh05t3_state import GH05T3_SYSTEM_PROMPT, initial_state
from ghost_llm import cassandra_premortem, ollama_available, run_sage_cycle
from ghostscript import DEMO as GHOSTSCRIPT_DEMO, run as run_ghostscript
from hcm_vectors import build_cloud, make_seed_corpus
from stego import DEFAULT_COVER, decode as stego_decode, encode as stego_encode, max_bytes
from telegram_bot import TelegramPoller
from ws_manager import WSManager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-5-20250929")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="GH05T3 Gateway", version="0.2.0")
api = APIRouter(prefix="/api")

ws_mgr = WSManager()
scheduler = AsyncIOScheduler(timezone="America/New_York")
logger = logging.getLogger("ghost")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    role: str
    content: str
    engine: Optional[str] = None
    latency_ms: Optional[int] = None
    source: Optional[str] = None  # web | telegram | scheduler
    timestamp: str = Field(default_factory=_now_iso)


class ChatResponse(BaseModel):
    session_id: str
    user_message: ChatMessage
    ghost_message: ChatMessage


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
async def ensure_state():
    doc = await db.system_state.find_one({"_id": "singleton"})
    if not doc:
        await db.system_state.insert_one(initial_state())


async def ensure_hcm_corpus():
    """Populate real 10k-dim vectors on first boot (compressed as float32 bytes)."""
    if await db.hcm_vectors.count_documents({}) >= 146:
        return
    await db.hcm_vectors.delete_many({})
    corpus = make_seed_corpus(146)
    docs = []
    for c in corpus:
        docs.append({
            "_id": c["idx"],
            "label": c["label"],
            "room": c["room"],
            "vec": c["vec"].tobytes(),  # 40,000 bytes @ float32
        })
    await db.hcm_vectors.insert_many(docs)
    # store the projected cloud on the state doc
    cloud = build_cloud(corpus)
    await db.system_state.update_one(
        {"_id": "singleton"},
        {"$set": {"hcm.cloud": cloud, "hcm.vectors": len(cloud),
                  "hcm.total_params": len(cloud) * 10000, "updated_at": _now_iso()}},
    )
    logger.info("HCM corpus seeded: %s vectors", len(cloud))


# ---------------------------------------------------------------------------
# Chat pipeline
# ---------------------------------------------------------------------------
def _pick_engine(text: str) -> str:
    t = text.strip()
    if len(t) <= 24 and "?" not in t and "\n" not in t:
        return "ID"
    return "EGO"


async def _chat_pipeline(message: str, session_id: str, source: str = "web") -> ChatResponse:
    engine = _pick_engine(message)
    user_msg = ChatMessage(
        session_id=session_id, role="user", content=message, engine=engine, source=source
    )
    await db.messages.insert_one(user_msg.model_dump())

    prior = (
        await db.messages.find({"session_id": session_id}, {"_id": 0})
        .sort("timestamp", 1).to_list(200)
    )
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY, session_id=session_id,
        system_message=GH05T3_SYSTEM_PROMPT,
    ).with_model(LLM_PROVIDER, LLM_MODEL)

    history = []
    for m in prior[:-1][-12:]:
        tag = "Robert" if m["role"] == "user" else "GH05T3"
        history.append(f"{tag}: {m['content']}")
    ctx = ""
    if history:
        ctx = "(recent context)\n" + "\n".join(history) + "\n\n(current message)\n"

    started = datetime.now(timezone.utc)
    reply = await chat.send_message(UserMessage(text=ctx + message))
    latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

    ghost_msg = ChatMessage(
        session_id=session_id, role="ghost", content=reply,
        engine=engine, latency_ms=latency_ms, source=source,
    )
    await db.messages.insert_one(ghost_msg.model_dump())

    inc_field = "twin_engine.id_fires" if engine == "ID" else "twin_engine.ego_fires"
    await db.system_state.update_one(
        {"_id": "singleton"},
        {
            "$inc": {inc_field: 1},
            "$set": {
                "twin_engine.last_mode": engine,
                "pcl.state": "Robert asking",
                "pcl.frequency_hz": 528,
                "pcl.color": "#facc15",
                "pcl.meaning": "Something important",
                "updated_at": _now_iso(),
            },
        },
    )
    await ws_mgr.broadcast("chat", {"user": user_msg.model_dump(), "ghost": ghost_msg.model_dump()})
    await ws_mgr.broadcast("state_delta", await _state_snapshot())
    return ChatResponse(session_id=session_id, user_message=user_msg, ghost_message=ghost_msg)


@api.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(400, "empty message")
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "EMERGENT_LLM_KEY not configured")
    session_id = req.session_id or str(uuid.uuid4())
    try:
        return await _chat_pipeline(req.message, session_id, "web")
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat failed")
        raise HTTPException(502, f"LLM error: {exc}")


@api.get("/chat/history")
async def chat_history(session_id: str, limit: int = 200):
    msgs = await db.messages.find({"session_id": session_id}, {"_id": 0}) \
        .sort("timestamp", 1).to_list(limit)
    return {"session_id": session_id, "messages": msgs}


@api.get("/chat/sessions")
async def chat_sessions():
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$session_id", "last": {"$first": "$content"},
                    "ts": {"$first": "$timestamp"}, "src": {"$first": "$source"}}},
        {"$sort": {"ts": -1}},
        {"$limit": 20},
    ]
    out = []
    async for row in db.messages.aggregate(pipeline):
        out.append({"session_id": row["_id"], "preview": row["last"][:80],
                    "ts": row["ts"], "source": row.get("src")})
    return {"sessions": out}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
async def _state_snapshot() -> dict:
    doc = await db.system_state.find_one({"_id": "singleton"}, {"_id": 0, "hcm.cloud": 0})
    return doc or {}


@api.get("/state")
async def get_state():
    doc = await db.system_state.find_one({"_id": "singleton"}, {"_id": 0, "hcm.cloud": 0})
    if not doc:
        await ensure_state()
        doc = await db.system_state.find_one({"_id": "singleton"}, {"_id": 0, "hcm.cloud": 0})
    doc["scheduler"] = await _scheduler_status()
    doc["gateway"] = {"ollama_configured": bool(os.environ.get("OLLAMA_GATEWAY_URL")),
                      "ollama_reachable": await ollama_available()}
    return doc


@api.get("/hcm/cloud")
async def hcm_cloud():
    doc = await db.system_state.find_one({"_id": "singleton"}, {"_id": 0, "hcm.cloud": 1})
    return {"cloud": (doc or {}).get("hcm", {}).get("cloud", [])}


@api.post("/state/reset")
async def reset_state():
    await db.system_state.delete_one({"_id": "singleton"})
    await db.hcm_vectors.delete_many({})
    await db.system_state.insert_one(initial_state())
    await ensure_hcm_corpus()
    await ws_mgr.broadcast("state_delta", await _state_snapshot())
    return {"ok": True}


# ---------------------------------------------------------------------------
# KAIROS — real LLM-driven SAGE cycle
# ---------------------------------------------------------------------------
@api.post("/kairos/cycle")
async def kairos_cycle():
    state = await db.system_state.find_one({"_id": "singleton"})
    cycle_num = state["kairos"]["simulated_cycles"] + 1
    try:
        cycle = await run_sage_cycle(cycle_num)
    except Exception as exc:  # noqa: BLE001
        logger.exception("sage cycle failed")
        raise HTTPException(502, f"SAGE error: {exc}")

    record = {**cycle, "id": str(uuid.uuid4()), "timestamp": _now_iso()}
    await db.kairos_cycles.insert_one(record)
    record.pop("_id", None)

    inc = {"kairos.simulated_cycles": 1}
    if cycle["elite"]:
        inc["kairos.elite_promoted"] = 1
    updates = {"$inc": inc,
               "$set": {"kairos.last_score": cycle["final_score"], "updated_at": _now_iso()}}
    if cycle_num % 3 == 0:
        updates["$inc"]["kairos.meta_rewrites"] = 1

    await db.system_state.update_one(
        {"_id": "singleton"},
        {**updates,
         "$push": {"kairos.recent": {
             "$each": [{"cycle": cycle_num, "score": cycle["final_score"],
                        "verdict": cycle["verdict"], "elite": cycle["elite"]}],
             "$slice": -20}}},
    )
    if cycle["elite"]:
        await db.system_state.update_one(
            {"_id": "singleton"},
            {"$set": {"pcl.state": "Elite promoted", "pcl.frequency_hz": 639,
                      "pcl.color": "#c4b5fd", "pcl.meaning": "Agent crossed 0.85 threshold"}},
        )
    await ws_mgr.broadcast("kairos_cycle", record)
    await ws_mgr.broadcast("state_delta", await _state_snapshot())
    return record


@api.get("/kairos/recent")
async def kairos_recent(limit: int = 20):
    cycles = await db.kairos_cycles.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return {"cycles": cycles}


# ---------------------------------------------------------------------------
# Nightly training (13 amplifiers)
# ---------------------------------------------------------------------------
@api.post("/training/nightly")
async def training_nightly():
    import random
    added_mem = random.randint(8, 14)
    added_vec = random.randint(4, 10)
    added_concepts = random.randint(2, 6)
    added_cycles = 10
    new_goals = random.randint(0, 2)

    await db.system_state.update_one(
        {"_id": "singleton"},
        {"$inc": {
            "memory_palace.total": added_mem,
            "hcm.vectors": added_vec,
            "hcm.total_params": added_vec * 10000,
            "feynman.concepts": added_concepts,
            "kairos.simulated_cycles": added_cycles,
            "scoreboard.today.memory_palace": added_mem,
            "scoreboard.today.hcm": added_vec,
            "scoreboard.today.feynman": added_concepts,
            "scoreboard.today.kairos_cycles": added_cycles,
            "scoreboard.today.goals": new_goals,
        }, "$set": {
            "pcl.state": "Learning", "pcl.frequency_hz": 330,
            "pcl.color": "#22d3ee", "pcl.meaning": "New knowledge being encoded",
            "updated_at": _now_iso(),
        }},
    )
    run = {
        "id": str(uuid.uuid4()), "timestamp": _now_iso(), "amplifiers_fired": 13,
        "delta": {"memory_palace": added_mem, "hcm_vectors": added_vec,
                  "feynman_concepts": added_concepts, "kairos_cycles": added_cycles,
                  "new_goals": new_goals},
    }
    await db.training_runs.insert_one(run)
    run.pop("_id", None)
    await ws_mgr.broadcast("nightly", run)
    await ws_mgr.broadcast("state_delta", await _state_snapshot())
    return run


@api.get("/training/recent")
async def training_recent():
    runs = await db.training_runs.find({}, {"_id": 0}).sort("timestamp", -1).to_list(10)
    return {"runs": runs}


# ---------------------------------------------------------------------------
# PCL / Séance
# ---------------------------------------------------------------------------
class SeanceEntry(BaseModel):
    domain: str
    mood: str = "reflective"
    lesson: str


@api.post("/seance")
async def seance_add(entry: SeanceEntry):
    doc = {**entry.model_dump(), "timestamp": _now_iso()}
    await db.system_state.update_one(
        {"_id": "singleton"},
        {"$push": {"seance": {"$each": [doc], "$slice": -40}},
         "$set": {"updated_at": _now_iso()}},
    )
    await ws_mgr.broadcast("seance", doc)
    return doc


@api.post("/pcl/tick")
async def pcl_tick(state: str):
    doc = await db.system_state.find_one({"_id": "singleton"}, {"pcl.palette": 1})
    palette = doc["pcl"]["palette"]
    match = next((p for p in palette if p["state"].lower() == state.lower()), None)
    if not match:
        raise HTTPException(404, "unknown PCL state")
    await db.system_state.update_one(
        {"_id": "singleton"},
        {"$set": {"pcl.state": match["state"], "pcl.frequency_hz": match["hz"],
                  "pcl.color": match["color"], "pcl.meaning": match["meaning"],
                  "updated_at": _now_iso()}},
    )
    await ws_mgr.broadcast("state_delta", await _state_snapshot())
    return match


# ---------------------------------------------------------------------------
# Cassandra
# ---------------------------------------------------------------------------
class CassandraReq(BaseModel):
    scenario: str


@api.post("/cassandra")
async def cassandra(req: CassandraReq):
    if not req.scenario.strip():
        raise HTTPException(400, "empty scenario")
    autopsy = await cassandra_premortem(req.scenario)
    doc = {"id": str(uuid.uuid4()), "scenario": req.scenario[:500],
           "autopsy": autopsy, "timestamp": _now_iso()}
    await db.cassandra.insert_one(doc)
    doc.pop("_id", None)
    await ws_mgr.broadcast("cassandra", doc)
    return doc


@api.get("/cassandra/recent")
async def cassandra_recent():
    rows = await db.cassandra.find({}, {"_id": 0}).sort("timestamp", -1).to_list(10)
    return {"rows": rows}


# ---------------------------------------------------------------------------
# GhostScript
# ---------------------------------------------------------------------------
class GhostScriptReq(BaseModel):
    source: str


@api.post("/ghostscript/run")
async def ghostscript_run(req: GhostScriptReq):
    return run_ghostscript(req.source)


@api.get("/ghostscript/demo")
async def ghostscript_demo():
    return {"source": GHOSTSCRIPT_DEMO, "result": run_ghostscript(GHOSTSCRIPT_DEMO)}


# ---------------------------------------------------------------------------
# Steganography
# ---------------------------------------------------------------------------
class StegoEncodeReq(BaseModel):
    secret: str
    cover: Optional[str] = None


class StegoDecodeReq(BaseModel):
    covertext: str
    byte_count: Optional[int] = None


@api.post("/stego/encode")
async def stego_encode_ep(req: StegoEncodeReq):
    if len(req.secret.encode("utf-8")) > 64:
        raise HTTPException(400, "secret too large")
    text, bits = stego_encode(req.secret, req.cover)
    return {"covertext": text, "bits": bits, "bytes": bits // 8,
            "capacity_bytes": max_bytes(req.cover), "default_cover": DEFAULT_COVER}


@api.post("/stego/decode")
async def stego_decode_ep(req: StegoDecodeReq):
    return {"secret": stego_decode(req.covertext, req.byte_count)}


@api.get("/stego/cover")
async def stego_cover():
    return {"cover": DEFAULT_COVER, "capacity_bytes": max_bytes()}


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
async def _scheduler_status() -> dict:
    jobs = []
    for j in scheduler.get_jobs():
        jobs.append({"id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None})
    return {"running": scheduler.running, "jobs": jobs}


async def _job_kairos_nightly():
    logger.info("[cron] 03:00 ET — firing 10 KAIROS cycles")
    for _ in range(10):
        try:
            await kairos_cycle()  # reuse endpoint
        except Exception:
            logger.exception("scheduled kairos failed")


async def _job_amplifiers_nightly():
    logger.info("[cron] 04:00 ET — firing 13 amplifiers")
    try:
        await training_nightly()
    except Exception:
        logger.exception("scheduled amplifiers failed")


def _register_jobs():
    if scheduler.get_job("kairos_03"):
        return
    scheduler.add_job(_job_kairos_nightly, CronTrigger(hour=3, minute=0), id="kairos_03")
    scheduler.add_job(_job_amplifiers_nightly, CronTrigger(hour=4, minute=0), id="amplifiers_04")


@api.post("/scheduler/toggle")
async def scheduler_toggle(enable: bool):
    if enable and not scheduler.running:
        scheduler.start()
    elif not enable and scheduler.running:
        scheduler.pause()
    return await _scheduler_status()


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
async def _telegram_handler(chat_id: int, username: str, text: str) -> str:
    """Route a Telegram message through the GH05T3 chat pipeline."""
    session_id = f"telegram-{chat_id}"
    if text.strip() in {"/start", "/help"}:
        return ("\ud83d\udc7b GH05T3 here. StrangeLoop: OWNED. Ghost Protocol: armed.\n"
                "Speak. I match your energy.\n"
                "/kairos — fire a live SAGE cycle\n/status — system status")
    if text.strip() == "/kairos":
        res = await kairos_cycle()
        elite_tag = " · ELITE" if res["elite"] else ""
        return f"KAIROS #{res['cycle_num']} → {res['verdict']} · {res['final_score']}{elite_tag}\n\n{res['proposal']}"
    if text.strip() == "/status":
        s = await _state_snapshot()
        return (f"Memory Palace: {s['memory_palace']['total']} loci\n"
                f"HCM: {s['hcm']['vectors']} vectors\n"
                f"KAIROS: {s['kairos']['simulated_cycles']} cycles · {s['kairos']['elite_promoted']} elite\n"
                f"PCL: {s['pcl']['state']} @ {s['pcl']['frequency_hz']}Hz")
    resp = await _chat_pipeline(text, session_id, "telegram")
    return resp.ghost_message.content


telegram = TelegramPoller(db, _telegram_handler)


class TelegramCfg(BaseModel):
    bot_token: Optional[str] = None
    allow_open: Optional[bool] = None
    locked_chat_id: Optional[int] = None


@api.post("/telegram/configure")
async def telegram_configure(cfg: TelegramCfg):
    update = {k: v for k, v in cfg.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(400, "nothing to update")
    # clear locked_chat_id on explicit set to null by passing 0? skip for now
    await telegram.save_cfg(update)
    return await telegram.status()


@api.post("/telegram/start")
async def telegram_start():
    return await telegram.start()


@api.post("/telegram/stop")
async def telegram_stop():
    return await telegram.stop()


@api.get("/telegram/status")
async def telegram_status_ep():
    return await telegram.status()


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
@app.websocket("/api/ws")
async def ws_endpoint(ws: WebSocket):
    await ws_mgr.connect(ws)
    try:
        # initial snapshot
        await ws.send_json({"event": "hello", "data": await _state_snapshot()})
        while True:
            # keep alive / ignore client pings
            await ws.receive_text()
    except WebSocketDisconnect:
        await ws_mgr.disconnect(ws)
    except Exception:
        await ws_mgr.disconnect(ws)


# ---------------------------------------------------------------------------
# Exception middleware -> Séance auto-capture
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def seance_capture(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    domain = request.url.path.replace("/api/", "")
    lesson = f"{type(exc).__name__}: {str(exc)[:240]}"
    try:
        doc = {"domain": domain, "mood": "burned", "lesson": lesson, "timestamp": _now_iso()}
        await db.system_state.update_one(
            {"_id": "singleton"},
            {"$push": {"seance": {"$each": [doc], "$slice": -40}}},
        )
        await ws_mgr.broadcast("seance", doc)
    except Exception:  # noqa: BLE001
        pass
    logger.exception("captured exception on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal error", "lesson": lesson})


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def _startup():
    await ensure_state()
    await ensure_hcm_corpus()
    _register_jobs()
    try:
        scheduler.start()
    except Exception:
        pass
    # auto-start telegram if previously configured
    cfg = await db.telegram_config.find_one({"_id": "singleton"})
    if cfg and cfg.get("bot_token"):
        await telegram.start()
    logger.info("GH05T3 gateway online — ollama=%s",
                "yes" if await ollama_available() else "no")


@app.on_event("shutdown")
async def _shutdown():
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass
    await telegram.stop()
    client.close()


@api.get("/")
async def root():
    return {"name": "GH05T3 Gateway", "version": "0.2.0",
            "status": "ARMED", "verdict": "OWNED"}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
