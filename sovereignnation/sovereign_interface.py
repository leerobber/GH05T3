"""
sovereign_interface.py â€” Unified Interface Layer
Port: 8100

Intent â†’ Genomic Dispatch â†’ Execution (Ollama) â†’ MCP Enrichment â†’ Novelty Feedback â†’ Genome Mutation

Endpoints:
  POST /intent             â€” main dispatch; returns response + genome_snapshot + novelty
  GET  /agents             â€” leaderboard with fitness/loyalty/genome summary
  GET  /genome/{agent_id} â€” full molecule snapshot for one agent
  POST /evolve             â€” trigger one manual evolution cycle
  POST /theory-lab/run    â€” psychology pressure lane (OmniSentientEcosystem.run_cycle)
  GET  /genome-stream      â€” WebSocket; broadcasts molecule metrics every 3s
  GET  /health
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# â”€â”€ Genomic imports â€” resolve path regardless of cwd (canonical: backend/oss/genomic) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from backend.oss.genomic import (
    Agent,
    AgentSwarm,
    LoyaltySystem,
    NoveltyRewardEngine,
    OmniSentientEcosystem,
    create_hyper_elite_psychology_genome,
)
from backend.oss.genomic.schema import LocusType

log = logging.getLogger("sovereign_interface")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")

NPU_SERVICE  = "http://127.0.0.1:8111"
OLLAMA_URL   = "http://localhost:11434"
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:12b")
OLLAMA_TIMEOUT_S = float(os.environ.get("OLLAMA_TIMEOUT_S", "300"))
OLLAMA_NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "400"))
_FALLBACK_MODELS = ("llama3.2:3b", "qwen2.5:7b", "llama3.2:latest", "gemma3:12b")

# â”€â”€ Locus routing map â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_ROUTE_TO_LOCUS: dict[str, str] = {
    "oracle":   LocusType.COGNITIVE.value,
    "forge":    LocusType.MARKET.value,
    "codex":    LocusType.META.value,
    "nexus":    LocusType.COMMUNICATION.value,
    "sentinel": LocusType.LOYALTY.value,
    "web_engineer_elite": LocusType.META.value,
}

# â”€â”€ Genome-derived system prompt fragments â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _render_genome_prompt(agent: Agent, route: str, loyalty_level: str = "novice") -> str:
    g = agent.genome
    lineage_id = f"{agent.agent_id}_g{g.generation}"
    lines = [
        f"You are {agent.agent_id.upper()} â€” sovereign agent class: {route}.",
        f"LOYALTY_LEVEL: {loyalty_level} | LINEAGE_ID: {lineage_id} | GENERATION: {g.generation}",
        "Use only provided context. Do not invent citations, URLs, p-values, or gene names not in the genome snapshot.",
    ]

    if g.get_value("psychology", "M_REASONING_DEPTH") > 0.8:
        lines.append("Reason step-by-step. Show your work before stating conclusions.")
    if g.get_value("psychology", "M_CURIOSITY_TRIGGER") > 0.8:
        lines.append("Frame responses to surface non-obvious insights the user has not considered.")
    if g.get_value("psychology", "M_TRUST_TONE") > 0.8:
        lines.append("Cite evidence and acknowledge uncertainty explicitly â€” never false confidence.")
    if g.get_value("psychology", "M_RISK_TOLERANCE") > 0.7:
        lines.append("Lead with aggressive risk assessment before any positive framing.")
    if g.get_value("psychology", "M_EMOTIONAL_CHARGE") > 0.7:
        lines.append("Use precise, high-stakes language. Avoid hedge words.")
    if g.get_value("cognitive", "M_LOGICAL_RIGOR") > 0.8:
        lines.append("Every claim requires a number, citation, or causal chain.")
    if g.get_value("cognitive", "M_CAUSAL_INFERENCE") > 0.75:
        lines.append("Identify root causes. Correlations are not conclusions.")

    loyalty = agent.genome.get_locus_score("loyalty")
    if loyalty > 0.7:
        lines.append(f"[Loyalty score: {loyalty:.2f}] Prioritize long-term value over short-term wins.")

    return "\n".join(lines)


# â”€â”€ Sovereign agent seed factory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _seed_agents() -> tuple[AgentSwarm, OmniSentientEcosystem]:
    eco = OmniSentientEcosystem()

    specs = [
        ("oracle",             0.15, 0.00, 0.10, 0.00),  # (id, cognitive, market, meta, loyalty bias)
        ("forge",              0.00, 0.15, 0.05, 0.00),
        ("codex",              0.10, 0.00, 0.15, 0.00),
        ("nexus",              0.05, 0.05, 0.05, 0.05),
        ("sentinel",           0.00, 0.00, 0.05, 0.15),
        ("web_engineer_elite", 0.12, 0.05, 0.18, 0.00),
    ]
    for agent_id, cog, mkt, meta, loy in specs:
        # AUTO-DISABLED by GH05T3 aggressive engine: genome = create_hyper_elite_psychology_genome(
        pass  # safe placeholder
            agent_id,
            cognitive_bias=cog,
            market_bias=mkt,
            meta_bias=meta,
            loyalty_bias=loy,
        )
        route = next((r for r, _ in [
            ("oracle", LocusType.COGNITIVE),
            ("forge",  LocusType.MARKET),
            ("codex",  LocusType.META),
        ] if r == agent_id), "oracle")
        agent = Agent(agent_id=agent_id, genome=genome, role=agent_id)
        eco.register(agent)

    return eco.swarm, eco


_SWARM, _ECO = _seed_agents()
_NOVELTY      = NoveltyRewardEngine()

# â”€â”€ FastAPI app â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app = FastAPI(title="SovereignInterface", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# â”€â”€ Pydantic models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class IntentRequest(BaseModel):
    text:    str
    context: dict = {}
    model:   str  = DEFAULT_MODEL

class EvolveRequest(BaseModel):
    pressure_type: str = "general"
    tasks:         List[str] = []

class TheoryLabRequest(BaseModel):
    pressure_type: str        = "psychology"
    tasks:         List[str]  = []
    cycles:        int        = 1

class ProposeRequest(BaseModel):
    agent_id:       str
    proposal_type:  str = "new_molecule"
    molecule:       str = ""
    locus:          str = ""
    description:    str = ""
    evidence:       dict = {}


# â”€â”€ Internal helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async def _classify_intent(text: str) -> tuple[str, list]:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(f"{NPU_SERVICE}/intent", json={"query": text, "model": "minilm"})
        if r.status_code == 200:
            data = r.json()
            return data.get("agent", "oracle"), []
    except Exception:
        pass
    return "oracle", []


async def _ollama_installed_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
        if r.status_code != 200:
            return []
        return [m.get("name", "") for m in r.json().get("models", []) if m.get("name")]
    except Exception:
        return []


def _resolve_ollama_model(requested: str, installed: list[str]) -> str:
    if not installed:
        return requested
    if requested in installed:
        return requested
    # Ollama tag aliases: "qwen2.5:7b" may be stored as "qwen2.5:7b" only â€” try prefix match
    for name in installed:
        if name == requested or name.startswith(requested.split(":")[0]):
            return name
    for candidate in _FALLBACK_MODELS:
        if candidate in installed:
            return candidate
    return installed[0]


def _format_exec_error(exc: Exception, *, model: str, resolved: str, elapsed_ms: int) -> tuple[str, dict]:
    """httpx.ReadTimeout stringifies to '' â€” always surface type + actionable hint."""
    name = type(exc).__name__
    detail = str(exc).strip() or "no detail"
    meta = {
        "error_type": name,
        "error_detail": detail,
        "requested_model": model,
        "resolved_model": resolved,
        "elapsed_ms": elapsed_ms,
    }
    if name in ("ReadTimeout", "ConnectTimeout", "WriteTimeout", "PoolTimeout"):
        msg = (
            f"[Ollama timeout after {elapsed_ms}ms ({OLLAMA_TIMEOUT_S:.0f}s limit): "
            f"model={resolved}. Local inference is slow â€” try llama3.2:3b, shorten the prompt, "
            f"or set OLLAMA_TIMEOUT_S=600.]"
        )
    elif name in ("ConnectError", "NetworkError"):
        msg = f"[Ollama unreachable at {OLLAMA_URL}: {detail}. Is `ollama serve` running?]"
    else:
        msg = f"[execution error: {name}: {detail}]"
    return msg, meta


async def _execute(system_prompt: str, text: str, model: str) -> tuple[str, dict]:
    installed = await _ollama_installed_models()
    resolved = _resolve_ollama_model(model, installed)
    payload = {
        "model":    resolved,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": text},
        ],
        "stream":  False,
        "keep_alive": "10m",
        "options": {"num_predict": OLLAMA_NUM_PREDICT, "temperature": 0.7},
    }
    t0 = time.time()
    try:
        timeout = httpx.Timeout(OLLAMA_TIMEOUT_S, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        elapsed = time.time() - t0
        if r.status_code != 200:
            detail = r.text.strip()
            try:
                detail = r.json().get("error", detail)
            except Exception:
                pass
            hint = ""
            if r.status_code == 404 and installed:
                hint = f" Installed: {', '.join(installed)}. Set model in Intent Console or run: ollama pull {model}"
            return f"[Ollama error {r.status_code}: {detail}.{hint}]", {
                "requested_model": model,
                "resolved_model":  resolved,
                "installed_models": installed,
            }
        data    = r.json()
        content = data.get("message", {}).get("content", "")
        eval_c  = data.get("eval_count", 0)
        eval_d  = data.get("eval_duration", 1) or 1
        meta = {
            "elapsed_ms": round(elapsed * 1000),
            "tok_per_sec": round(eval_c / (eval_d / 1e9), 1),
            "model": resolved,
        }
        if resolved != model:
            meta["requested_model"] = model
        return content, meta
    except Exception as e:
        elapsed_ms = round((time.time() - t0) * 1000)
        log.warning("Ollama execute failed model=%s resolved=%s: %s", model, resolved, e)
        return _format_exec_error(e, model=model, resolved=resolved, elapsed_ms=elapsed_ms)


async def _enrich_via_mcp(agent: Agent, route: str, raw: str, context: dict) -> str:
    """Only call MCP if agent's META reasoning_depth >= 0.7 â€” cost gate."""
    depth = agent.genome.get_value("meta", "M_REASONING_DEPTH")
    if depth < 0.7:
        return raw
    # Placeholder: real MCP call would go here (tool: search / code_analysis / market_data)
    tool = {"oracle": "search", "codex": "code_analysis", "forge": "market_data"}.get(route)
    if not tool:
        return raw
    log.debug("MCP enrichment â€” agent=%s tool=%s depth=%.2f", agent.agent_id, tool, depth)
    return raw   # enrichment injected here in production


# â”€â”€ Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.get("/health")
async def health():
    installed = await _ollama_installed_models()
    return {
        "status":    "ok",
        "agents":    len(_SWARM.all()),
        "cycle":     _ECO._cycle,
        "port":      8100,
        "ollama": {
            "url":            OLLAMA_URL,
            "default_model":  DEFAULT_MODEL,
            "installed":      installed,
            "timeout_s":      OLLAMA_TIMEOUT_S,
            "num_predict":    OLLAMA_NUM_PREDICT,
        },
    }


@app.post("/intent")
async def intent_dispatch(req: IntentRequest):
    route, _ = await _classify_intent(req.text)
    locus_key = _ROUTE_TO_LOCUS.get(route, LocusType.COGNITIVE.value)
    agent = _SWARM.select_by_locus(locus_key)
    if agent is None:
        return JSONResponse(status_code=503, content={"error": "no agents registered"})

    loyalty_level = _ECO.loyalty.get_level(agent.agent_id).value
    system_prompt = _render_genome_prompt(agent, route, loyalty_level)
    response_text, exec_meta = await _execute(system_prompt, req.text, req.model)
    enriched = await _enrich_via_mcp(agent, route, response_text, req.context)

    metrics = {
        "task_success": 0.75,
        "user_rating":  req.context.get("user_rating", 0.6),
        "latency_ms":   exec_meta.get("elapsed_ms", 1000),
        "coherence":    0.7,
    }
    fitness = agent.genome.calculate_fitness(metrics)
    agent.record_fitness(fitness)

    novelty = _NOVELTY.compute_reward(
        agent_id=agent.agent_id,
        output=enriched,
        metrics=metrics,
        context=req.context,
    )
    agent.genome.mutate(context={"novelty_reward": novelty.weighted})

    _ECO.loyalty.record(
        agent_id=agent.agent_id,
        fitness_history=agent.fitness_history,
        user_rating=metrics["user_rating"],
    )

    # Async write to genomic training JSONL
    asyncio.create_task(_write_training_record(agent, route, req.text, enriched, fitness, novelty))

    return {
        "agent_id":        agent.agent_id,
        "route":           route,
        "response":        enriched,
        "fitness":         fitness,
        "novelty_score":   novelty.weighted,
        "loyalty_level":   _ECO.loyalty.get_level(agent.agent_id).value,
        "genome_snapshot": agent.genome.snapshot(),
        "exec_meta":       exec_meta,
    }


@app.get("/agents")
async def list_agents():
    return {"agents": _SWARM.leaderboard()}


@app.get("/genome/{agent_id}")
async def genome_snapshot(agent_id: str):
    agent = _SWARM.get(agent_id)
    if not agent:
        return JSONResponse(status_code=404, content={"error": f"agent {agent_id!r} not found"})
    return {
        **agent.profile(_ECO.loyalty),
        "genome":  agent.genome.snapshot(),
        "novelty": {a_id: len(nd._history) for a_id, nd in _NOVELTY.detectors.items()},
    }


@app.post("/propose")
async def submit_proposal(req: ProposeRequest):
    """Loyalty-gated evolution proposal â€” requires evidence block, rejects hallucinated genes."""
    agent = _SWARM.get(req.agent_id)
    if not agent:
        return JSONResponse(status_code=404, content={"error": f"agent {req.agent_id!r} not found"})

    evidence = dict(req.evidence)
    if not evidence.get("fitness_history") and agent.fitness_history:
        evidence.setdefault("fitness_history", agent.fitness_history[-10:])
    evidence.setdefault("generation", agent.genome.generation)
    evidence.setdefault("mean_fitness", round(agent.mean_fitness(), 4))

    ok, result = _ECO.loyalty.propose_change(
        req.agent_id,
        req.proposal_type,
        lineage_id=f"{req.agent_id}_g{agent.genome.generation}",
        generation=agent.genome.generation,
        molecule=req.molecule,
        locus=req.locus,
        description=req.description,
        evidence=evidence,
    )
    if not ok:
        return JSONResponse(status_code=403, content={"error": result, "loyalty_level": _ECO.loyalty.get_level(req.agent_id).value})
    return {"proposal_id": result, "status": "pending", "agent_id": req.agent_id}


@app.get("/proposals")
async def list_proposals(agent_id: Optional[str] = None):
    return {"proposals": _ECO.loyalty.list_proposals(agent_id)}


@app.post("/evolve")
async def trigger_evolve(req: EvolveRequest):
    result = await _ECO.run_cycle(
        pressure_type=req.pressure_type,
        tasks=req.tasks or None,
    )
    return result


@app.post("/theory-lab/run")
async def theory_lab_run(req: TheoryLabRequest):
    """Psychology pressure lane â€” runs N cycles with psychology-biased tasks."""
    results = []
    for i in range(max(1, min(req.cycles, 10))):
        result = await _ECO.run_cycle(
            pressure_type=req.pressure_type,
            tasks=req.tasks or None,
        )
        results.append(result)
    return {
        "cycles_run":   len(results),
        "pressure_type": req.pressure_type,
        "results":       results,
        "population":    _ECO.population_snapshot(),
    }


@app.websocket("/genome-stream")
async def genome_stream(ws: WebSocket):
    """Streams molecule metrics for all agents every 3 seconds."""
    await ws.accept()
    try:
        while True:
            payload = {
                "ts":   time.time(),
                "agents": [
                    {
                        "agent_id":    a.agent_id,
                        "generation":  a.genome.generation,
                        "fitness_ema": round(a.fitness_ema(), 4),
                        "loyalty":     _ECO.loyalty.get_level(a.agent_id).value,
                        "snapshot":    a.genome.snapshot(),
                    }
                    for a in _SWARM.all()
                ],
            }
            await ws.send_text(json.dumps(payload))
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        log.info("genome-stream client disconnected")


# â”€â”€ Training JSONL writer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_TRAINING_PATH = _ROOT / "backend" / "data" / "training" / "genomic_snapshots.jsonl"


async def _write_training_record(agent, route, prompt, response, fitness, novelty) -> None:
    _TRAINING_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "agent_id":  agent.agent_id,
        "route":     route,
        "prompt":    prompt,
        "response":  response,
        "fitness":   fitness,
        "novelty":   novelty.weighted,
        "discovery": novelty.discovery,
        "generation": agent.genome.generation,
        "loyalty":   _ECO.loyalty.get_level(agent.agent_id).value,
        "snapshot":  agent.genome.snapshot(),
        "ts":        time.time(),
    }
    try:
        with open(_TRAINING_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("genomic_snapshots.jsonl write failed: %s", e)


# â”€â”€ Entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100, reload=False)
