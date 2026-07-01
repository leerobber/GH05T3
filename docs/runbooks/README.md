# Runbooks

Operational procedures, troubleshooting, and recovery steps.

## Core

- Starting the stack: see `run_stack.py --help`, `RUN_ORDER.md`, `native/windows/START_ALL.bat`
- Health & smoke: `.claude/skills/run-gh05t3/driver.py health|smoke`
- Stopping: run_stack.py --stop or supervisor --stop
- Port conflicts / zombies: manual netstat + kill (document common PIDs)

## Common issues

- Gateway zombie (listens but refuses): restart via run.bat or manual kill
- Backend blocked on slow Ollama: use TCP health, wait or set COST_FREE_ONLY + faster model
- Training paths: always use scripts/ subdirs from repo root

Add specific runbooks here (e.g. `recovery-after-crash.md`, `rotate-llm-keys.md`).
