"""
GH05T3 backend \u2014 FastAPI gateway.
Chat runs through emergentintegrations (Claude Sonnet 4.5 today, swappable to
local Ollama endpoints later via LLM_PROVIDER / LLM_MODEL env vars).
All architecture state persists in MongoDB.
"""
import os
import random
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware

from emergentintegrations.llm.chat import LlmChat, UserMessage

from gh05t3_state import GH05T3_SYSTEM_PROMPT, initial_state

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-5-20250929")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="GH05T3 Gateway", version="0.1.0")
api = APIRouter(prefix="/api")


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
    role: str  # "user" | "ghost"
    content: str
    engine: Optional[str] = None  # "ID" | "EGO"
    latency_ms: Optional[int] = None
    timestamp: str = Field(default_factory=_now_iso)


class ChatResponse(BaseModel):
    session_id: str
    user_message: ChatMessage
    ghost_message: ChatMessage


# ---------------------------------------------------------------------------
# State bootstrap
# ---------------------------------------------------------------------------
async def ensure_state():
    doc = await db.system_state.find_one({"_id": "singleton"})
    if not doc:
        await db.system_state.insert_one(initial_state())


@app.on_event("startup")
async def _startup():
    await ensure_state()


@app.on_event("shutdown")
async def _shutdown():
    client.close()


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
def _pick_engine(text: str) -> str:
    """Twin Engine heuristic: short/routine \u2192 ID, otherwise EGO (Ego wins conflicts)."""
    t = text.strip()
    if len(t) <= 24 and "?" not in t and "\n" not in t:
        return "ID"
    return "EGO"


@api.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(400, "empty message")
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "EMERGENT_LLM_KEY not configured")

    session_id = req.session_id or str(uuid.uuid4())
    engine = _pick_engine(req.message)

    # persist user message
    user_msg = ChatMessage(
        session_id=session_id, role="user", content=req.message, engine=engine
    )
    await db.messages.insert_one(user_msg.model_dump())

    # load prior messages for this session (newest last)
    prior = (
        await db.messages.find({"session_id": session_id}, {"_id": 0})
        .sort("timestamp", 1)
        .to_list(200)
    )

    chat_obj = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=GH05T3_SYSTEM_PROMPT,
    ).with_model(LLM_PROVIDER, LLM_MODEL)

    started = datetime.now(timezone.utc)
    try:
        # emergentintegrations LlmChat keeps its own per-instance history, but
        # since we make a new instance per request we replay the last turns as
        # a compact context prefix in the user message.
        history_lines = []
        for m in prior[:-1][-12:]:  # last 12 turns, excluding the message we just added
            tag = "Robert" if m["role"] == "user" else "GH05T3"
            history_lines.append(f"{tag}: {m['content']}")
        ctx = ""
        if history_lines:
            ctx = "(recent context)\n" + "\n".join(history_lines) + "\n\n(current message)\n"
        response_text = await chat_obj.send_message(UserMessage(text=ctx + req.message))
    except Exception as exc:  # noqa: BLE001
        logging.exception("llm call failed")
        raise HTTPException(502, f"LLM error: {exc}")

    latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

    ghost_msg = ChatMessage(
        session_id=session_id,
        role="ghost",
        content=response_text,
        engine=engine,
        latency_ms=latency_ms,
    )
    await db.messages.insert_one(ghost_msg.model_dump())

    # Bump Twin Engine counters & PCL state
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

    return ChatResponse(session_id=session_id, user_message=user_msg, ghost_message=ghost_msg)


@api.get("/chat/history")
async def chat_history(session_id: str, limit: int = 200):
    msgs = (
        await db.messages.find({"session_id": session_id}, {"_id": 0})
        .sort("timestamp", 1)
        .to_list(limit)
    )
    return {"session_id": session_id, "messages": msgs}


@api.get("/chat/sessions")
async def chat_sessions():
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$session_id", "last": {"$first": "$content"}, "ts": {"$first": "$timestamp"}}},
        {"$sort": {"ts": -1}},
        {"$limit": 20},
    ]
    out = []
    async for row in db.messages.aggregate(pipeline):
        out.append({"session_id": row["_id"], "preview": row["last"][:80], "ts": row["ts"]})
    return {"sessions": out}


# ---------------------------------------------------------------------------
# System state
# ---------------------------------------------------------------------------
@api.get("/state")
async def get_state():
    doc = await db.system_state.find_one({"_id": "singleton"}, {"_id": 0})
    if not doc:
        await ensure_state()
        doc = await db.system_state.find_one({"_id": "singleton"}, {"_id": 0})
    return doc


# ---------------------------------------------------------------------------
# KAIROS / SAGE simulated cycle
# ---------------------------------------------------------------------------
class KairosCycle(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cycle_num: int
    proposer: str
    critic: str
    verifier: str
    proposal: str
    verdict: str  # PASS | PARTIAL | FAIL
    critic_decision: str  # APPROVE | REJECT | REVISE
    base_score: float
    multiplier: float
    final_score: float
    archived: bool
    elite: bool
    timestamp: str = Field(default_factory=_now_iso)


PROPOSALS = [
    "Switch KAIROS archive to FAISS HNSW \u2014 O(log N) search",
    "Add diversity bonus to score: +0.05 per novel domain touched",
    "Coder sub-agent: 3-attempt self-revise with pytest gating",
    "Steganographic channel: bias token 37/1000 for covert ACK",
    "RFFingerprint 15MHz probe \u2192 trigger GhostVeil decoys",
    "Cross-domain transfer: apply VRAM patterns to latency",
    "Meta-Agent rewrite: penalize critic-capture \u00d7 0.3 multiplier",
    "DGM stepping stones feed KAIROS archive nightly at 03:30 ET",
    "S\u00e9ance \u2192 Distiller auto-synthesis every 5 failures",
    "Constitutional critique: Critic outputs structured JSON, not binary",
]


@api.post("/kairos/cycle")
async def run_kairos_cycle():
    state = await db.system_state.find_one({"_id": "singleton"})
    cycle_num = state["kairos"]["simulated_cycles"] + 1

    verdict = random.choices(["PASS", "PARTIAL", "FAIL"], weights=[55, 30, 15])[0]
    critic_decision = random.choices(["APPROVE", "REJECT", "REVISE"], weights=[60, 25, 15])[0]
    base = {"PASS": 1.0, "PARTIAL": 0.6, "FAIL": 0.2}[verdict]
    mult = {"APPROVE": 1.0, "REJECT": 0.5, "REVISE": 0.75}[critic_decision]
    final = round(base * mult, 3)
    elite = final >= 0.85
    archived = final >= 0.70 or (verdict == "PASS")

    cycle = KairosCycle(
        cycle_num=cycle_num,
        proposer="Qwen2.5 @ RTX 5050",
        critic="Claude-Sonnet @ Gateway",
        verifier="DeepSeek-Coder @ Radeon 780M",
        proposal=random.choice(PROPOSALS),
        verdict=verdict,
        critic_decision=critic_decision,
        base_score=base,
        multiplier=mult,
        final_score=final,
        archived=archived,
        elite=elite,
    )
    await db.kairos_cycles.insert_one(cycle.model_dump())

    inc = {"kairos.simulated_cycles": 1}
    if elite:
        inc["kairos.elite_promoted"] = 1
    # meta-rewrite every 3rd cycle
    updates = {"$inc": inc, "$set": {"kairos.last_score": final, "updated_at": _now_iso()}}
    if cycle_num % 3 == 0:
        updates["$inc"]["kairos.meta_rewrites"] = 1

    # push recent (cap 10)
    await db.system_state.update_one(
        {"_id": "singleton"},
        {
            **updates,
            "$push": {
                "kairos.recent": {
                    "$each": [{"cycle": cycle_num, "score": final, "verdict": verdict, "elite": elite}],
                    "$slice": -10,
                }
            },
        },
    )
    # PCL flips to elite-promoted on promotion
    if elite:
        await db.system_state.update_one(
            {"_id": "singleton"},
            {"$set": {"pcl.state": "Elite promoted", "pcl.frequency_hz": 639,
                      "pcl.color": "#c4b5fd", "pcl.meaning": "Agent crossed 0.85 threshold"}},
        )

    return cycle.model_dump()


@api.get("/kairos/recent")
async def kairos_recent(limit: int = 20):
    cycles = await db.kairos_cycles.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return {"cycles": cycles}


# ---------------------------------------------------------------------------
# Nightly training (13 amplifiers)
# ---------------------------------------------------------------------------
@api.post("/training/nightly")
async def run_nightly():
    state = await db.system_state.find_one({"_id": "singleton"})
    added_mem = random.randint(8, 14)
    added_vec = random.randint(4, 10)
    added_concepts = random.randint(2, 6)
    added_cycles = 10  # 10 simulated ARSO cycles
    new_goals = random.randint(0, 2)

    await db.system_state.update_one(
        {"_id": "singleton"},
        {
            "$inc": {
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
            },
            "$set": {
                "pcl.state": "Learning",
                "pcl.frequency_hz": 330,
                "pcl.color": "#22d3ee",
                "pcl.meaning": "New knowledge being encoded",
                "updated_at": _now_iso(),
            },
        },
    )

    run = {
        "id": str(uuid.uuid4()),
        "timestamp": _now_iso(),
        "amplifiers_fired": 13,
        "delta": {
            "memory_palace": added_mem,
            "hcm_vectors": added_vec,
            "feynman_concepts": added_concepts,
            "kairos_cycles": added_cycles,
            "new_goals": new_goals,
        },
    }
    await db.training_runs.insert_one(run)
    run.pop("_id", None)
    return run


@api.get("/training/recent")
async def training_recent():
    runs = await db.training_runs.find({}, {"_id": 0}).sort("timestamp", -1).to_list(10)
    return {"runs": runs}


# ---------------------------------------------------------------------------
# PCL + S\u00e9ance endpoints
# ---------------------------------------------------------------------------
class SeanceEntry(BaseModel):
    domain: str
    mood: str = "reflective"
    lesson: str


@api.post("/seance")
async def add_seance(entry: SeanceEntry):
    doc = entry.model_dump()
    doc["timestamp"] = _now_iso()
    await db.system_state.update_one(
        {"_id": "singleton"},
        {"$push": {"seance": {"$each": [doc], "$slice": -30}}, "$set": {"updated_at": _now_iso()}},
    )
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
        {"$set": {
            "pcl.state": match["state"],
            "pcl.frequency_hz": match["hz"],
            "pcl.color": match["color"],
            "pcl.meaning": match["meaning"],
            "updated_at": _now_iso(),
        }},
    )
    return match


@api.post("/state/reset")
async def reset_state():
    await db.system_state.delete_one({"_id": "singleton"})
    await db.system_state.insert_one(initial_state())
    return {"ok": True}


@api.get("/")
async def root():
    return {"name": "GH05T3 Gateway", "status": "ARMED", "verdict": "OWNED"}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
