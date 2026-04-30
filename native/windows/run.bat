@echo off
REM GH05T3 v3 — launcher. Double-click or auto-run on login.
REM This file is copied to the repo root by install.ps1.
setlocal enableextensions

set APP=%~dp0
cd /d "%APP%"

REM Ensure runtime dirs exist
if not exist "%APP%mongo-data"        mkdir "%APP%mongo-data"
if not exist "%APP%backend\memory"    mkdir "%APP%backend\memory"
if not exist "%APP%backend\evolution" mkdir "%APP%backend\evolution"

set PY=%APP%backend\.venv\Scripts\python

REM ── MongoDB :27017 ───────────────────────────────────────────────────────
start "gh05t3-mongo" /min mongod --dbpath "%APP%mongo-data" --bind_ip 127.0.0.1 --port 27017 --quiet
timeout /t 2 /nobreak > nul

REM ── server.py :8001  (existing FastAPI + MongoDB backend) ────────────────
start "gh05t3-backend" /min /d "%APP%backend" "%PY%" -m uvicorn server:app --host 127.0.0.1 --port 8001

REM ── gateway_v3 :8002  (SwarmBus · Claude API · GitHub automation) ────────
start "gh05t3-gateway-v3" /min /d "%APP%backend" "%PY%" -m uvicorn gateway_v3:app --host 127.0.0.1 --port 8002

REM ── Frontend static bundle :3210 ─────────────────────────────────────────
start "gh05t3-frontend" /min "%PY%" -m http.server 3210 --directory "%APP%frontend\build"

REM ── Whisper listener ─────────────────────────────────────────────────────
start "gh05t3-whisper" /min "%PY%" "%APP%whisper_listener.py"

REM ── Tray icon (blocks — keeps this window as the host process) ────────────
"%PY%" "%APP%tray.py"

endlocal
