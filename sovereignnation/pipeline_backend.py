"""
pipeline_backend.py — GH05T3 Business Intelligence Pipeline backend
Run: uvicorn pipeline_backend:app --host 0.0.0.0 --port 8099

Bridges the 48hr_poc_agent_pipeline.html -> Ollama (local, free)
No Anthropic. No API key. No cost.

Port: 8099 (port 8000 is occupied by GH05T3 gateway)
"""
import time
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

OLLAMA_URL = "http://localhost:11434"

app = FastAPI()

# -- CORS: allow browser requests from any origin (file://, localhost, etc.) --
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- Health check -- also returns available Ollama models --------------------
@app.get("/health")
async def health():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
        models = [m["name"] for m in r.json().get("models", [])]
        return {"status": "ok", "models_available": models}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": str(e)}
        )


# -- Chat endpoint -- accepts HTML format, converts to Ollama, returns result -
@app.post("/chat")
async def chat(request: Request):
    body = await request.json()

    model      = body.get("model", "qwen2.5:7b")
    system     = body.get("system", "")
    messages   = body.get("messages", [])
    max_tokens = body.get("max_tokens", 800)

    # Build Ollama message list (system prompt as first message)
    ollama_messages = []
    if system:
        ollama_messages.append({"role": "system", "content": system})
    ollama_messages.extend(messages)

    payload = {
        "model": model,
        "messages": ollama_messages,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.7,
        }
    }

    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        elapsed = round(time.time() - t0, 2)

        if r.status_code != 200:
            return JSONResponse(
                status_code=r.status_code,
                content={"error": r.text[:400]}
            )

        data    = r.json()
        content = data.get("message", {}).get("content", "")

        # tok/s from Ollama eval stats
        eval_count    = data.get("eval_count", 0)
        eval_duration = data.get("eval_duration", 1)  # nanoseconds
        tps = round(eval_count / (eval_duration / 1e9), 1) if eval_duration else 0

        return {
            "message": {"content": content},
            "tok_per_sec": tps,
            "elapsed_seconds": elapsed,
        }

    except httpx.ConnectError:
        return JSONResponse(
            status_code=503,
            content={"error": "Cannot connect to Ollama. Is it running? (ollama serve)"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8099, reload=False)
