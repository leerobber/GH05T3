Production Python patterns used across the GH05T3 and agent-economy codebase.

## When to apply
When writing or reviewing Python code for any GH05T3 service.

## FastAPI patterns
- Always use `BackgroundTasks` for post-response work (never block the response)
- Use `httpx.AsyncClient(timeout=N)` — never default timeout, always set explicitly
- Graceful degradation: if NPU service down, fall back to Ollama — never hard-fail
- Log with `log.info()` not `print()` — use the module-level logger pattern

## Ollama integration
```python
# Standard Ollama chat call
async with httpx.AsyncClient(timeout=120) as client:
    r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
if r.status_code != 200:
    return JSONResponse(status_code=r.status_code, content={"error": r.text[:400]})
data = r.json()
content = data.get("message", {}).get("content", "")
```

## Tool-call loop pattern (OpenClaw Pi style)
```python
for turn in range(max_turns):
    response = await ollama_chat(messages, tools=TOOLS)
    if not response.get("tool_calls"):
        return response  # done
    results = execute_tools(response["tool_calls"])
    messages.append(tool_result_message(results))
```

## ChromaDB pattern
```python
import chromadb
from chromadb.config import Settings
chroma = chromadb.PersistentClient(
    path="../local-ai-mesh/data/vectors",
    settings=Settings(anonymized_telemetry=False)
)
collection = chroma.get_or_create_collection("knowledge_base")
```

## Subprocess safety
- Always set timeout=30 on subprocess.run()
- Always capture_output=True, text=True
- Check for dangerous patterns before executing
- Use WORK_DIR as default cwd, not os.getcwd()

## Error handling hierarchy
1. httpx.ConnectError → 503 with "service down" message
2. Timeout → 504 with "timed out" message
3. JSON decode error → log and return empty/default
4. General Exception → 500 with str(e)[:200]
