GH05T3 system architecture — ports, services, files, and patterns to follow when modifying code.

## When to apply
Every time you're asked to modify, debug, or extend any GH05T3 or agent-economy service.

## Critical rules
- PORT 8000 IS PERMANENTLY LOCKED — never use it, never suggest it
- Never use 'rm -rf' on anything in the GH05T3 or agent-economy directories
- Always read existing files before modifying them
- Run `curl http://localhost:8081/health` to verify economy API is alive before changes

## Port registry (from PORT_REGISTRY.md)
- 8000: LOCKED (system)
- 8001: backend
- 8002: gateway
- 3210: frontend
- 7861: serve.py (Ollama proxy)
- 7862: payments
- 8081: economy-api
- 8090: supervisor
- 8099: pipeline-backend ← THIS FILE'S SERVICE
- 8111: npu-embed (ryzen-ai conda env)
- 8765: landing-server
- 27017: MongoDB

## Key file locations
- Economy API: `C:\Users\leer4\Documents\agent-economy\`
- GH05T3 stack: `C:\Users\leer4\GH05T3\`
- Pipeline backend: `C:\Users\leer4\GH05T3\sovereignnation\pipeline_backend.py`
- NPU service: `C:\Users\leer4\GH05T3\sovereignnation\npu_embedding_service.py`
- Local AI mesh: `C:\Users\leer4\Documents\local-ai-mesh\`
- Skills (this system): `C:\Users\leer4\GH05T3\sovereignnation\skills\`

## Coding patterns in this codebase
- FastAPI + httpx (async) for all services
- SQLite + SQLAlchemy for agent economy DB
- ChromaDB for vector storage (path: `../local-ai-mesh/data/vectors`)
- Ollama at localhost:11434 — KEEP_ALIVE=10m, MAX_LOADED_MODELS=1
- NPU embedding service at 127.0.0.1:8111 — always try NPU first, fallback to Ollama

## Restarting services
- Supervisor controls all services: `http://localhost:8090`
- To restart pipeline-backend: POST to supervisor restart endpoint or kill/relaunch uvicorn
- Economy auto-runner: check `Get-Process python | Where CommandLine -like '*auto_runner*'`

## Model names in Ollama
- Main: `qwen2.5:7b`
- Vision: `moondream`
- Avery: `avery-sovereign` (7B Q4_K_M)
- Specialists: `forge-sovereign`, `oracle-sovereign`, `codex-sovereign`, `nexus-sovereign` (1.5B Q8)
