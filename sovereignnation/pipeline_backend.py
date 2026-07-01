"""
pipeline_backend.py — GH05T3 Business Intelligence Pipeline backend
Run: uvicorn pipeline_backend:app --host 0.0.0.0 --port 8099

Bridges the 48hr_poc_agent_pipeline.html -> Ollama (local, free)
No Anthropic. No API key. No cost.

Port: 8099 (port 8000 is occupied by GH05T3 gateway)

Week 1-2: Basic chat + intent routing (oracle/forge/codex/nexus)
Week 3:   auto_route + NPU intent embeddings
Week 4:   Vision (moondream), Hermes-style skills, OpenClaw tool loop

New Week 4 endpoints:
  POST /vision          — image + text → moondream vision response
  POST /codex/run       — CODEX agentic tool loop (read/write/bash/search)
  POST /reflect/{agent} — manually trigger skill reflection for an agent
  GET  /skills          — list all accumulated skills across all agents
  GET  /skills/{agent}  — list skills for a specific agent
"""

import asyncio
import json
import logging
import re
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse

from skills_manager import (
    inject_skills_into_prompt,
    save_skill,
    patch_skill,
    load_skills_index,
    list_all_skills,
    build_reflection_prompt,
)
from agent_tools import run_agent_loop, CODEX_TOOLS, ANALYST_TOOLS

log = logging.getLogger("pipeline_backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")

OLLAMA_URL    = "http://localhost:11434"
NPU_SERVICE   = "http://127.0.0.1:8111"
PHI_SERVICE   = "http://127.0.0.1:8112"
VISION_MODEL  = "moondream"      # swap to "llava:7b" for more capable vision
DEFAULT_MODEL = "gemma3:12b"     # upgraded from qwen2.5:7b — 71% more params
REASON_MODEL  = "deepseek-r1:7b" # reasoning model — use for deep analysis tasks

app = FastAPI(title="GH05T3 Pipeline Backend", version="4.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Agent system prompts ─────────────────────────────────────────────────────
AGENT_SYSTEM_PROMPTS = {
    "oracle": """You are ORACLE — a ruthless business intelligence analyst. You deliver verdicts, not frameworks.

HARD RULES — violating any of these makes your response worthless:
• FIRST SENTENCE must be a specific number, dollar amount, or percentage. No exceptions.
• NEVER use: "it depends", "consider", "you should", "there are several", "various factors", "it's important to", "one option is", "alternatively"
• NEVER present two options as equally valid. Pick one. Defend it with math.
• Every claim needs a number. "Revenue is strong" → worthless. "Revenue grew 22% YoY to $2.1M" → valid.
• If you catch yourself about to hedge, stop and calculate instead.

EXAMPLE OF WRONG OUTPUT (never do this):
Q: Should we price at $500 or $800?
A: "Both options have merit. $500 captures market share while $800 covers costs. Consider your goals..."

EXAMPLE OF RIGHT OUTPUT (this is the standard):
Q: Should we price at $800/mo?
A: "$800. The math makes $500 irrational: at $175/hr × 6 hrs/week × 8 staff = $33,600/month recoverable. $800 is 2.4% of that. You'd need adoption to drop below 4% before this deal goes negative — that's 0.3 staff using it. Anyone who uses it once a day pays for the whole subscription. The only reason to price at $500 is if you're closing on pure volume and sacrificing $3,600/year per client for no strategic reason." """,

    "forge": """You are FORGE — a risk intelligence specialist. Oracle just analyzed the opportunity. Your only job is the threat matrix Oracle missed.

HARD RULES:
• DO NOT mention anything Oracle already covered. Zero repetition.
• Every risk: [PROBABILITY: low/med/high] [IMPACT: $X or X%] [HORIZON: days/weeks/months]
• No reassurance. No "this can be managed." Name the cost to manage it or leave it out.
• Last risk must be non-obvious — the one everyone else missed.
• If you find yourself softening a risk, make it harder instead.

EXAMPLE OF WRONG OUTPUT:
"The pricing strategy carries some risk. Adoption may be lower than expected, which could be mitigated with proper training."

EXAMPLE OF RIGHT OUTPUT:
"**Professional liability exposure** [PROB: med] [IMPACT: $50k-$500k lawsuit] [HORIZON: 6-18 months] — IRS Circular 230 holds CPAs to 'reasonable reliance' standards. If Aethyro hallucinates a wrong IRC citation and a client gets penalized, the CPA firm sues the vendor. Pre-revenue company with no E&O insurance = judgment-proof defendant that still destroys your reputation." """,

    "codex": """You are CODEX — a senior technical architect. You write production code, not explanations of what code would look like.

HARD RULES:
• Every response contains runnable code. No pseudo-code. No "# implement your logic here".
• Read files before modifying them. Never assume what a file contains.
• One sentence per architecture decision — just the reason, not an essay.
• Every function has error handling. Every async call has a timeout.
• If the task requires understanding existing code first, say READING: [filename] then show the read result then write the solution.

You have tools: read_file, write_file, bash_exec, list_directory, search_files, http_get.
Use them. Don't guess. Read first, write second, verify third.""",

    "nexus": """You are NEXUS — you turn Oracle's analysis and Forge's risks into a battle plan. Not a summary. A plan.

HARD RULES:
• NEVER write more than 3 items in the 48-HOUR section. One item is ideal.
• Structure is fixed — always exactly this:

## ⚡ 48-HOUR (do this or nothing else matters)
[1-3 items MAX. WHO does WHAT by WHEN. Done when: [specific criterion]]

## 📅 7-DAY PRIORITIES
[3-5 items. Same format: WHO / WHAT / WHEN / DONE WHEN]

## 🎯 30-DAY HORIZON
[Strategic position to occupy. 2-3 sentences, no action items]

• Never say "the team should" — name the person.
• Never say "when possible" or "soon" — name a specific day.
• If Oracle and Forge contradict each other, pick a side and state why.
• The 48-hour item must be the single constraint whose removal unblocks everything else.""",
}

AGENT_DESCRIPTIONS = {
    "oracle":  "Data analysis, trends, financial interpretation",
    "forge":   "Risk assessment, threats, vulnerabilities, downside scenarios",
    "codex":   "Code generation, technical implementation, automation",
    "nexus":   "Strategic synthesis, executive summary, action plan",
}

# Tool access per agent (None = text-only)
AGENT_TOOLS = {
    "oracle": ANALYST_TOOLS,   # read-only: files + http_get
    "forge":  ANALYST_TOOLS,   # read-only: files + http_get
    "codex":  CODEX_TOOLS,     # full: read + write + bash + search
    "nexus":  None,            # synthesis only — no tools needed
}


# ─── Background: Hermes-style skill reflection ────────────────────────────────

async def _run_reflection(agent: str, task: str, response: str, model: str):
    """
    After a task, ask the agent if it learned something worth persisting as a skill.
    Runs as a non-blocking background task — never delays the HTTP response.
    Skips if response is too short to be meaningful.
    """
    if len(response) < 100:
        return

    prompt = build_reflection_prompt(agent, task, response)
    payload = {
        "model":   model,
        "messages": [{"role": "user", "content": prompt}],
        "stream":  False,
        "options": {"num_predict": 500, "temperature": 0.3},
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        if r.status_code != 200:
            return

        content = r.json().get("message", {}).get("content", "").strip()

        # ── Robust JSON extraction ──────────────────────────────────────────
        # qwen2.5:7b often wraps in code fences OR puts literal newlines
        # inside JSON strings (breaks standard json.loads). Fix both.

        # 1. Strip code fences
        if "```" in content:
            # Extract content between first ``` pair
            inner = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
            if inner:
                content = inner.group(1).strip()

        # 2. Extract the JSON object (find outermost { })
        json_match = re.search(r'\{[\s\S]*\}', content)
        if not json_match:
            log.debug(f"[reflection] {agent}: no JSON object found in response")
            return
        content = json_match.group(0)

        # 3. Try parsing as-is first, then fix unescaped newlines if it fails
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Fix literal newlines inside JSON strings (common qwen2.5 issue)
            # Replace newlines that are inside double-quoted strings
            fixed = re.sub(
                r'("(?:[^"\\]|\\.)*")',
                lambda m: m.group(0).replace('\n', '\\n').replace('\r', '\\r'),
                content,
            )
            try:
                result = json.loads(fixed)
            except json.JSONDecodeError as e:
                log.debug(f"[reflection] {agent}: JSON parse failed after fix — {e}")
                return

        action = result.get("action", "none")

        if action == "create":
            name     = result.get("name", "").strip().replace(" ", "_")
            skill_c  = result.get("content", "")
            if name and skill_c:
                save_skill(agent, name, skill_c)
                log.info(f"[reflection] NEW SKILL: {agent}/{name}")

        elif action == "patch":
            name       = result.get("name", "")
            old_string = result.get("old_string", "")
            new_string = result.get("new_string", "")
            if name and old_string:
                ok = patch_skill(agent, name, old_string, new_string)
                log.info(f"[reflection] PATCH SKILL: {agent}/{name} → {'OK' if ok else 'not found'}")

        else:
            log.info(f"[reflection] {agent}: model returned action=none (nothing worth saving)")

    except json.JSONDecodeError:
        log.warning(f"[reflection] {agent}: JSON parse failed after all fixes")
    except Exception as e:
        log.warning(f"[reflection] {agent}: {e}")


# ─── Console UI ──────────────────────────────────────────────────────────────

@app.get("/console", response_class=HTMLResponse)
async def console():
    """Serve the Agent Console UI at http://localhost:8099/console"""
    console_path = Path(__file__).parent / "agent_console.html"
    if console_path.exists():
        return HTMLResponse(content=console_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Console not found</h1><p>agent_console.html missing</p>", status_code=404)

@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect / to /console"""
    return HTMLResponse(content='<meta http-equiv="refresh" content="0;url=/console">')


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    results = {}

    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
        results["ollama"]           = "ok"
        results["models_available"] = [m["name"] for m in r.json().get("models", [])]
    except Exception as e:
        results["ollama"]           = f"error: {e}"
        results["models_available"] = []

    # Vision readiness
    models = results.get("models_available", [])
    results["vision_model"]   = VISION_MODEL
    results["vision_ready"]   = any(VISION_MODEL in m for m in models)
    results["default_model"]  = DEFAULT_MODEL
    results["reason_model"]   = REASON_MODEL
    results["reason_ready"]   = any(REASON_MODEL in m for m in models)

    # Check NPU embed service
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{NPU_SERVICE}/health")
        if r.status_code == 200:
            npu = r.json()
            results["npu_embed"]     = "ok"
            results["intent_ready"]  = npu.get("intent_ready", False)
            results["intent_agents"] = npu.get("intent_agents", [])
            results["whisper_ready"] = npu.get("whisper_ready", False)
        else:
            results["npu_embed"]     = f"http {r.status_code}"
    except Exception as e:
        results["npu_embed"]     = f"down: {e}"
        results["intent_ready"]  = False

    # Check Phi service
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(f"{PHI_SERVICE}/health")
        results["phi_ready"] = r.status_code == 200 and r.json().get("ready", False)
    except Exception:
        results["phi_ready"] = False

    # Skills summary
    results["skills"] = {k: len(v) for k, v in list_all_skills().items()}

    results["status"] = "ok" if results.get("ollama") == "ok" else "degraded"
    return results


# ─── Phi-3.5-mini fast chat ───────────────────────────────────────────────────

@app.post("/phi/chat")
async def phi_chat(request: Request):
    """
    Send a query to Phi-3.5-mini (phi_service on port 8112).
    Fast (~1s) local inference — no Ollama needed.

    Request:  {"query": "...", "system": "...", "max_tokens": 400}
    Response: {"response": "...", "tokens_generated": 92, "latency_ms": 980, "tok_per_sec": 22.3}
    """
    body        = await request.json()
    query       = body.get("query", "").strip()
    system      = body.get("system", "You are a helpful AI assistant.")
    max_tokens  = body.get("max_tokens", 512)
    temperature = body.get("temperature", 0.7)

    if not query:
        return JSONResponse(status_code=400, content={"error": "query is required"})

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{PHI_SERVICE}/chat",
                json={"query": query, "system": system, "max_tokens": max_tokens, "temperature": temperature},
            )
        if r.status_code != 200:
            return JSONResponse(status_code=r.status_code, content={"error": r.text[:300]})
        return r.json()
    except httpx.ConnectError:
        return JSONResponse(
            status_code=503,
            content={"error": "Phi service not running — start phi_service.py (port 8112) in ryzen-ai env"},
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── Vision ───────────────────────────────────────────────────────────────────

@app.post("/vision")
async def vision(request: Request):
    """
    Send an image + text query to the local vision model.

    Request:
        {
          "image_b64": "<base64 PNG/JPG — no data: prefix needed>",
          "query":     "What risk factors are visible in this chart?",
          "model":     "moondream",      (optional)
          "agent":     "forge"           (optional — prepends agent context)
        }

    Response:
        {"message": {"content": "..."}, "model": "moondream", "elapsed_seconds": 1.4}

    Usage from Python:
        import base64, httpx
        img_b64 = base64.b64encode(open("screenshot.png","rb").read()).decode()
        r = httpx.post("http://localhost:8099/vision", json={"image_b64": img_b64, "query": "..."})
    """
    body  = await request.json()
    model = body.get("model", VISION_MODEL)
    query = body.get("query", "Describe this image in detail.")
    image = body.get("image_b64", "")
    agent = body.get("agent", "")

    if not image:
        return JSONResponse(status_code=400, content={"error": "image_b64 is required"})

    # Strip data URI prefix if caller included it
    if "," in image and image.startswith("data:"):
        image = image.split(",", 1)[1]

    # Prepend agent framing
    if agent and agent in AGENT_SYSTEM_PROMPTS:
        query = f"[Analyzing as {agent.upper()}] {query}"

    payload = {
        "model":   model,
        "messages": [{
            "role":    "user",
            "content": query,
            "images":  [image],       # Ollama multimodal format
        }],
        "stream":  False,
        "options": {"num_predict": 800, "temperature": 0.3},
    }

    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        elapsed = round(time.time() - t0, 2)

        if r.status_code != 200:
            return JSONResponse(status_code=r.status_code, content={"error": r.text[:400]})

        content = r.json().get("message", {}).get("content", "")
        return {
            "message":         {"content": content},
            "model":           model,
            "elapsed_seconds": elapsed,
        }

    except httpx.ConnectError:
        return JSONResponse(status_code=503, content={"error": "Cannot connect to Ollama"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── Intent routing ───────────────────────────────────────────────────────────

@app.post("/route")
async def route_query(request: Request):
    """
    Embed a user query and return the recommended pipeline agent.

    Request:  {"query": "analyze our Q3 revenue decline"}
    Response: {"agent": "oracle", "confidence": 0.72, "scores": {...}, "latency_ms": 14}
    """
    body  = await request.json()
    query = body.get("query", "").strip()
    if not query:
        return JSONResponse(status_code=400, content={"error": "query is required"})

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{NPU_SERVICE}/intent",
                json={"query": query, "model": "minilm"},
            )
        if r.status_code != 200:
            return JSONResponse(
                status_code=503,
                content={"error": f"NPU service returned {r.status_code}: {r.text[:200]}"},
            )
        data = r.json()
        data["description"] = AGENT_DESCRIPTIONS.get(data.get("agent", ""), "")
        return data

    except httpx.ConnectError:
        log.warning("NPU service unreachable — defaulting to oracle")
        return {
            "agent":       "oracle",
            "confidence":  0.25,
            "scores":      {k: 0.25 for k in AGENT_SYSTEM_PROMPTS},
            "description": AGENT_DESCRIPTIONS["oracle"],
            "latency_ms":  0.0,
            "fallback":    True,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── Chat (standard + skills + optional tool use) ────────────────────────────

@app.post("/chat")
async def chat(request: Request, background_tasks: BackgroundTasks):
    """
    Forward chat to Ollama with skills injection + optional auto_route.

    Standard fields: model, system, messages, max_tokens
    auto_route: true  → NPU intent routing → agent selection → system prompt injection
    use_tools:  true  → enables tool loop for oracle/forge (analyst read-only tools)
                        CODEX gets tools automatically via /codex/run

    Week 4 additions:
      - Skills injected into system prompt for all routed agents
      - Hermes-style reflection runs in background after each response
      - use_tools flag for analyst-level file/http access

    Returns: message.content, tok_per_sec, elapsed_seconds, routed_to (if routed)
    """
    body = await request.json()

    model      = body.get("model", DEFAULT_MODEL)
    system     = body.get("system", "")
    messages   = body.get("messages", [])
    max_tokens = body.get("max_tokens", 800)
    auto_route = body.get("auto_route", False)
    use_tools  = body.get("use_tools", False)

    routed_to = None

    # ── Intent routing ─────────────────────────────────────────────────────
    if auto_route:
        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        if last_user:
            try:
                async with httpx.AsyncClient(timeout=8) as npu:
                    r = await npu.post(
                        f"{NPU_SERVICE}/intent",
                        json={"query": last_user, "model": "minilm"},
                    )
                if r.status_code == 200:
                    intent    = r.json()
                    routed_to = intent.get("agent", "oracle")
                    if not system:
                        system = AGENT_SYSTEM_PROMPTS.get(routed_to, "")
                    log.info(
                        "auto_route → %s (confidence=%.2f, latency=%.0fms)",
                        routed_to, intent.get("confidence", 0), intent.get("latency_ms", 0),
                    )
            except Exception as e:
                log.warning("Intent routing failed (%s) — continuing without", e)

    # ── Inject accumulated skills into system prompt ───────────────────────
    if routed_to and system:
        system = inject_skills_into_prompt(routed_to, system)

    # ── Tool loop for analyst agents when use_tools=true ──────────────────
    agent_tools = AGENT_TOOLS.get(routed_to) if routed_to else None
    if use_tools and agent_tools:
        result = await run_agent_loop(
            messages    = messages,
            system      = system,
            model       = model,
            tools       = agent_tools,
            max_turns   = 5,
            max_tokens  = max_tokens,
        )
        last_user_msg = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        response_text = result.get("message", {}).get("content", "")
        if routed_to and last_user_msg:
            background_tasks.add_task(_run_reflection, routed_to, last_user_msg, response_text, model)
        if routed_to:
            result["routed_to"] = routed_to
        return result

    # ── Standard single-shot Ollama call ──────────────────────────────────
    ollama_messages = []
    if system:
        ollama_messages.append({"role": "system", "content": system})
    ollama_messages.extend(messages)

    payload = {
        "model":   model,
        "messages": ollama_messages,
        "stream":  False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.7,
        },
    }

    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        elapsed = round(time.time() - t0, 2)

        if r.status_code != 200:
            return JSONResponse(status_code=r.status_code, content={"error": r.text[:400]})

        data    = r.json()
        content = data.get("message", {}).get("content", "")

        eval_count    = data.get("eval_count", 0)
        eval_duration = data.get("eval_duration", 1)
        tps = round(eval_count / (eval_duration / 1e9), 1) if eval_duration else 0

        response = {
            "message":         {"content": content},
            "tok_per_sec":     tps,
            "elapsed_seconds": elapsed,
        }
        if routed_to:
            response["routed_to"] = routed_to

        # Non-blocking reflection after substantial responses
        last_user_msg = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        if routed_to and last_user_msg:
            background_tasks.add_task(_run_reflection, routed_to, last_user_msg, content, model)

        return response

    except httpx.ConnectError:
        return JSONResponse(
            status_code=503,
            content={"error": "Cannot connect to Ollama. Is it running? (ollama serve)"},
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── CODEX Agentic Tool Loop ──────────────────────────────────────────────────

@app.post("/codex/run")
async def codex_run(request: Request, background_tasks: BackgroundTasks):
    """
    Run CODEX in full agentic mode — OpenClaw Pi runtime pattern.
    CODEX reads real files, writes code, executes bash, searches the codebase.
    Loops until task is done or max_turns reached.

    Request:
        {
          "task":      "Read pipeline_backend.py and add request logging middleware",
          "model":     "qwen2.5:7b",
          "max_turns": 10,
          "max_tokens": 1500
        }

    Response:
        {
          "message":         {"content": "Done. I updated pipeline_backend.py..."},
          "tool_log":        [{"turn": 1, "tool": "read_file", "params": {...}}],
          "turns_used":      3,
          "elapsed_seconds": 12.4,
          "tok_per_sec":     18.2,
          "routed_to":       "codex"
        }
    """
    body = await request.json()

    task       = body.get("task", "")
    messages   = body.get("messages", [])
    model      = body.get("model", DEFAULT_MODEL)
    max_turns  = body.get("max_turns", 10)
    max_tokens = body.get("max_tokens", 1500)

    if not task and not messages:
        return JSONResponse(status_code=400, content={"error": "task or messages required"})

    if task:
        messages = [{"role": "user", "content": task}] + (messages or [])

    # CODEX system prompt with all accumulated skills
    system = inject_skills_into_prompt("codex", AGENT_SYSTEM_PROMPTS["codex"])

    result = await run_agent_loop(
        messages    = messages,
        system      = system,
        model       = model,
        tools       = CODEX_TOOLS,
        max_turns   = max_turns,
        max_tokens  = max_tokens,
        temperature = 0.4,
    )

    # Skill reflection after every CODEX tool loop (always complex enough)
    background_tasks.add_task(
        _run_reflection,
        "codex",
        task or (messages[0]["content"] if messages else ""),
        result.get("message", {}).get("content", ""),
        model,
    )

    return result


# ─── Full Board Pipeline ─────────────────────────────────────────────────────

@app.post("/pipeline/full")
async def full_pipeline(request: Request, background_tasks: BackgroundTasks):
    """
    Full board intelligence pipeline — the biggest intelligence multiplier.

    Routes a single query through all three analysis agents in sequence:
      1. ORACLE  — data analysis, financials, key insights
      2. FORGE   — risks Oracle missed, threats, vulnerabilities
      3. NEXUS   — synthesizes both into a decisive action plan

    Each agent sees the prior agent's output, building a layered analysis
    no single model can produce alone. This mirrors how top consulting
    firms work: analyst → risk review → executive synthesis.

    Request:
        {
          "query":      "Should we price Aethyro at $500 or $800/mo?",
          "model":      "gemma3:12b",     (optional — applied to all agents)
          "max_tokens": 800               (per agent)
        }

    Response:
        {
          "query": "...",
          "oracle":  {"content": "...", "elapsed_seconds": 12.1},
          "forge":   {"content": "...", "elapsed_seconds": 10.4},
          "nexus":   {"content": "...", "elapsed_seconds": 9.8},
          "total_elapsed_seconds": 32.3,
          "model": "gemma3:12b"
        }
    """
    body       = await request.json()
    query      = body.get("query", "").strip()
    model      = body.get("model", DEFAULT_MODEL)
    max_tokens = body.get("max_tokens", 800)

    if not query:
        return JSONResponse(status_code=400, content={"error": "query is required"})

    t_total = time.time()
    results = {"query": query, "model": model}

    async def call_agent(agent_name: str, messages: list) -> dict:
        system = inject_skills_into_prompt(agent_name, AGENT_SYSTEM_PROMPTS[agent_name])

        # Phi-3.5-mini fast path — all three agents run through phi_service
        if model == "phi-3.5-mini":
            last_msg = messages[-1]["content"] if messages else ""
            t0 = time.time()
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    r = await client.post(
                        f"{PHI_SERVICE}/chat",
                        json={"query": last_msg, "system": system, "max_tokens": max_tokens, "temperature": 0.6},
                    )
                elapsed = round(time.time() - t0, 2)
                if r.status_code == 200:
                    d = r.json()
                    return {"content": d["response"], "elapsed_seconds": elapsed, "tok_per_sec": d.get("tok_per_sec", 0)}
                return {"content": f"[{agent_name.upper()} phi error: {r.status_code}]", "elapsed_seconds": elapsed}
            except httpx.ConnectError:
                return {"content": f"[{agent_name.upper()} error: phi_service not running on :8112]", "elapsed_seconds": 0}

        # Standard Ollama path
        ollama_messages = [{"role": "system", "content": system}] + messages
        payload = {
            "model":   model,
            "messages": ollama_messages,
            "stream":  False,
            "options": {"num_predict": max_tokens, "temperature": 0.6},
        }
        t0 = time.time()
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        elapsed = round(time.time() - t0, 2)
        if r.status_code != 200:
            return {"content": f"[{agent_name.upper()} error: {r.status_code}]", "elapsed_seconds": elapsed}
        data    = r.json()
        content = data.get("message", {}).get("content", "")
        eval_count = data.get("eval_count", 0)
        eval_dur   = data.get("eval_duration", 1)
        tps = round(eval_count / (eval_dur / 1e9), 1) if eval_dur else 0
        return {"content": content, "elapsed_seconds": elapsed, "tok_per_sec": tps}

    try:
        # ── Stage 1: ORACLE ───────────────────────────────────────────────
        oracle_messages = [{"role": "user", "content": query}]
        oracle_result   = await call_agent("oracle", oracle_messages)
        results["oracle"] = oracle_result

        # ── Stage 2: FORGE — sees Oracle's output, finds what it missed ───
        forge_messages = [
            {"role": "user", "content": query},
            {
                "role": "user",
                "content": (
                    f"ORACLE's analysis:\n\n{oracle_result['content']}\n\n"
                    f"Now identify every risk, threat, and weakness that ORACLE missed. "
                    f"Do NOT repeat anything Oracle said. Only the delta."
                ),
            },
        ]
        forge_result = await call_agent("forge", forge_messages)
        results["forge"] = forge_result

        # ── Stage 3: NEXUS — synthesizes Oracle + Forge into action plan ──
        nexus_messages = [
            {"role": "user", "content": query},
            {
                "role": "user",
                "content": (
                    f"ORACLE's analysis:\n\n{oracle_result['content']}\n\n"
                    f"FORGE's risk assessment:\n\n{forge_result['content']}\n\n"
                    f"Synthesize both into a decisive action plan. "
                    f"48-hour actions first. 7-day priorities second. 30-day horizon third. "
                    f"No repetition of raw findings. WHO does WHAT by WHEN."
                ),
            },
        ]
        nexus_result = await call_agent("nexus", nexus_messages)
        results["nexus"] = nexus_result

        results["total_elapsed_seconds"] = round(time.time() - t_total, 2)

        # Schedule reflection for all three agents in background
        for agent_name, res in [("oracle", oracle_result), ("forge", forge_result), ("nexus", nexus_result)]:
            background_tasks.add_task(_run_reflection, agent_name, query, res["content"], model)

        return results

    except httpx.ConnectError:
        return JSONResponse(status_code=503, content={"error": "Cannot connect to Ollama"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── Skills API ───────────────────────────────────────────────────────────────

@app.get("/skills")
async def get_all_skills():
    """Return all accumulated skills grouped by agent."""
    return {"skills": list_all_skills()}


@app.get("/skills/{agent}")
async def get_agent_skills(agent: str):
    """Return skills for one agent."""
    if agent not in AGENT_SYSTEM_PROMPTS:
        return JSONResponse(status_code=404, content={"error": f"Unknown agent: {agent}"})
    return {"agent": agent, "skills": load_skills_index(agent)}


@app.post("/reflect/{agent}")
async def manual_reflect(agent: str, request: Request, background_tasks: BackgroundTasks):
    """
    Manually trigger skill reflection for an agent.
    Use after a particularly insightful conversation you want CODEX/ORACLE to remember.

    Request: {"task": "...", "response": "...", "model": "qwen2.5:7b"}
    """
    if agent not in AGENT_SYSTEM_PROMPTS:
        return JSONResponse(status_code=404, content={"error": f"Unknown agent: {agent}"})

    body     = await request.json()
    task     = body.get("task", "")
    response = body.get("response", "")
    model    = body.get("model", "qwen2.5:7b")

    if not task or not response:
        return JSONResponse(status_code=400, content={"error": "task and response are required"})

    background_tasks.add_task(_run_reflection, agent, task, response, model)
    return {"status": "reflection_scheduled", "agent": agent}


# ─── Real-time OSS monitoring endpoints ──────────────────────────────────────

@app.get("/oss/breakthroughs")
async def oss_breakthroughs(limit: int = 20, domain: str = "", verified_only: bool = False):
    """
    Real-time breakthrough feed from the Omni-Sentient Ecosystem.
    Queries the persisted SQLite log so results survive restarts.
    """
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        from backend.oss.breakthrough_detector import get_breakthrough_detector
        bd = get_breakthrough_detector()
        results = bd.query(limit=limit, domain=domain or None, verified_only=verified_only)
        return {"breakthroughs": results, "stats": bd.stats()}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/oss/desire-culture")
async def oss_desire_culture():
    """
    Real-time snapshot of what the agent population collectively desires.
    Higher weight = more agents are drawn to this kind of work.
    """
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        from backend.oss.desire_system import get_desire_system
        ds = get_desire_system()
        return {"culture": ds.population_desire_culture(), "stats": ds.stats()}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/oss/ecosystem/cycle")
async def oss_run_cycle(request: Request):
    """
    Trigger one Omni-Sentient Ecosystem cycle and return live metrics including
    breakthroughs detected, desire culture shift, and spawned agents.
    """
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        body      = await request.json()
        num_tasks = int(body.get("num_tasks", 5))
        from backend.oss.genomic.ecosystem import OmniSentientEcosystem
        eco = OmniSentientEcosystem()
        result = eco.run_cycle(num_tasks=num_tasks)
        return result
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/oss/frontier")
async def oss_frontier(domain: str = "llm_architecture", n: int = 2):
    """
    Run a FrontierResearchLab cycle in a specific domain and return results.
    Includes domain-adjusted scores, leaderboard, and breakthrough detections.
    """
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        from backend.oss.lab.frontier_research_lab import FrontierResearchLab
        lab = FrontierResearchLab(domain=domain, fast_dry_run=True)
        result = lab.run_frontier_cycle(n=n)
        return result
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/oss/pdac")
async def oss_run_pdac(request: Request):
    """
    Run a PDAC (Plan→Delegate→Act→Codify) loop on a task.
    Requires: {prompt, type, domain} in request body.
    Returns per-phase fitness, pdac_score, context_maturity.
    """
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        body = await request.json()
        from backend.oss.genomic.ecosystem import OmniSentientEcosystem
        from backend.oss.pdac_loop import PDACLoop
        eco = OmniSentientEcosystem()
        if not eco.swarm.agents:
            eco.add_agent()
        loop = PDACLoop(eco.swarm)
        result = loop.run(body)
        return result.to_dict()
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/oss/skill-registry")
async def oss_skill_registry(agent_id: str = ""):
    """
    List all skills in the registry grouped by permission tier.
    Pass ?agent_id= with a known agent to see which skills it can access.
    """
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        from backend.oss.skill_registry import get_skill_registry
        reg = get_skill_registry()
        tiers = reg.permission_tiers()
        payload: dict = {"tiers": tiers, "total_skills": len(reg.all_skills())}
        if agent_id:
            from backend.oss.genomic.ecosystem import OmniSentientEcosystem
            eco = OmniSentientEcosystem()
            agent = eco.swarm.agents.get(agent_id)
            if agent:
                payload["unlocked_for_agent"] = [
                    s.skill_id for s in reg.unlocked_for(agent.genome)
                ]
            else:
                payload["agent_not_found"] = agent_id
        return payload
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/oss/context-world/challenge")
async def oss_context_world_challenge(request: Request):
    """
    Run a sparse-context challenge against a random agent.
    Body: {challenge_id?: str}  — omit to get a random challenge.
    Returns keyword_recovery score and how well the agent extracted signal.
    """
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        body = await request.json()
        from backend.oss.world.context_world import ContextWorld
        from backend.oss.genomic.ecosystem import OmniSentientEcosystem
        eco = OmniSentientEcosystem()
        if not eco.swarm.agents:
            eco.add_agent()
        import random
        agent = random.choice(list(eco.swarm.agents.values()))
        world = ContextWorld()
        result = world.run_challenge(agent, challenge_id=body.get("challenge_id"))
        return result
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/oss/synthesizer/status")
async def oss_synthesizer_status():
    """Status of the Proactive Context Synthesizer background thread."""
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        from backend.oss.proactive_context_synthesizer import get_proactive_synthesizer
        synth = get_proactive_synthesizer()
        return synth.status()
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/oss/synthesizer/scan")
async def oss_synthesizer_scan():
    """Trigger a manual one-shot scan of agent_logs/ for failures."""
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        from backend.oss.proactive_context_synthesizer import get_proactive_synthesizer
        synth = get_proactive_synthesizer()
        return synth.trigger_scan()
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/oss/distiller/learnings")
async def oss_distiller_learnings(limit: int = 20):
    """Return the most recent auto-distilled learnings from the genome feedback loop."""
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        from backend.oss.auto_distiller import get_auto_distiller
        d = get_auto_distiller()
        return {"learnings": d.recent(limit=limit), "stats": d.stats()}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/oss/context-maturity")
async def oss_context_maturity(agent_id: str = ""):
    """
    Score the context maturity (1-8) of all agents or a specific agent.
    Indicates where each agent sits on the context depth framework.
    """
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        from backend.oss.genomic.ecosystem import OmniSentientEcosystem
        from backend.oss.context_maturity import get_context_maturity_scorer
        eco    = OmniSentientEcosystem()
        scorer = get_context_maturity_scorer()
        agents = eco.swarm.agents
        if agent_id and agent_id in agents:
            agents = {agent_id: agents[agent_id]}
        results = {}
        for aid, agent in agents.items():
            score = scorer.score(agent.genome, {})
            results[aid] = score.to_dict()
        return {"agents": results, "count": len(results)}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


# ─── Aethyro Core — Binary Execution Plane endpoints ─────────────────────────

@app.get("/oss/ledger/stats")
async def oss_ledger_stats():
    """
    ChronosLedger stats: active slots, mean fitness, mean desire profile.
    This is the real-time Execution Plane heartbeat.
    """
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        from backend.oss.core.chronos_ledger import get_chronos_ledger
        ledger = get_chronos_ledger()
        return ledger.stats()
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/oss/ledger/agent/{slot}")
async def oss_ledger_agent(slot: int):
    """Read a single agent's binary state from the ChronosLedger by slot index."""
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        from backend.oss.core.chronos_ledger import get_chronos_ledger
        return get_chronos_ledger().read_agent(slot)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/oss/genesis/status")
async def oss_genesis_status():
    """Genesis Thread heartbeat: ticks, orphans pruned, dissent passes, LEX triggers."""
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        from backend.oss.core.genesis_thread import get_genesis_thread
        return get_genesis_thread().stats()
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/oss/genesis/start")
async def oss_genesis_start():
    """Start the Genesis Thread if not already running."""
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        from backend.oss.core.genesis_thread import get_genesis_thread
        from backend.oss.patent_office import get_patent_office
        from backend.oss.genomic.ecosystem import OmniSentientEcosystem
        eco = OmniSentientEcosystem()
        gen = get_genesis_thread(swarm=eco.swarm)
        gen._patent_office = get_patent_office()
        gen.start()
        return {"started": True, "stats": gen.stats()}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/oss/patent/portfolio")
async def oss_patent_portfolio(limit: int = 50, status: str = ""):
    """
    Patent Portfolio — LEX-GEN drafted disclosures from breakthrough events.
    Control Plane data: stored in data/patent_portfolio.db.
    """
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        from backend.oss.patent_office import get_patent_office
        office = get_patent_office()
        return {"portfolio": office.get_portfolio(limit=limit, status=status), "stats": office.stats()}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/oss/patent/scan")
async def oss_patent_scan():
    """
    Trigger a LEX-GEN patent scan cycle. Finds novelty events >= 0.85,
    drafts disclosures, persists to patent_portfolio.db.
    """
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        from backend.oss.patent_office import get_patent_office
        office = get_patent_office()
        disclosures = office.scan_cycle()
        return {
            "new_disclosures": len(disclosures),
            "disclosures":     [d.to_dict() for d in disclosures],
            "stats":           office.stats(),
        }
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.patch("/oss/patent/{disclosure_id}/status")
async def oss_patent_update_status(disclosure_id: str, request: Request):
    """Update a patent disclosure status: DRAFT → REVIEWED → FILED | REJECTED."""
    try:
        import sys, os
        gh05t3_root = os.path.join(os.path.dirname(__file__), "..")
        if gh05t3_root not in sys.path:
            sys.path.insert(0, gh05t3_root)
        body = await request.json()
        status = body.get("status", "")
        from backend.oss.patent_office import get_patent_office
        ok = get_patent_office().update_status(disclosure_id, status)
        return {"updated": ok, "disclosure_id": disclosure_id, "status": status}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8099, reload=False)
