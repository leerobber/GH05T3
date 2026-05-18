@echo off
setlocal enableextensions
set APP=%~dp0
cd /d "%APP%"

echo === GH05T3 ===

REM ── Kill any leftover processes on our ports ──────────────────────────────
echo Clearing ports 8001 8002 3210...
for %%P in (8001 8002 3210) do (
    for /f "tokens=5" %%A in ('netstat -ano 2^>nul ^| findstr "0.0.0.0:%%P "') do (
        if not "%%A"=="0" taskkill /F /PID %%A >nul 2>&1
    )
)
timeout /t 2 >nul

REM ── Python: prefer venv ───────────────────────────────────────────────────
set PY=python
if exist "%APP%backend\.venv\Scripts\python.exe" (
    set PY=%APP%backend\.venv\Scripts\python.exe
)

REM ── Ollama: start if not running ──────────────────────────────────────────
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul 2>&1
if errorlevel 1 (
    echo Starting Ollama...
    start "ollama" /min ollama serve
    timeout /t 4 >nul
)

REM ── MongoDB ───────────────────────────────────────────────────────────────
echo Starting MongoDB...
if not exist "%APP%mongo-data" mkdir "%APP%mongo-data"
start "mongo" mongod --dbpath "%APP%mongo-data" --port 27017 --bind_ip 127.0.0.1
timeout /t 3 >nul

REM ── Backend: server.py (economy engine, CFO, Telegram) ───────────────────
echo Starting backend:8001...
start "backend" cmd /c "cd /d "%APP%backend" && "%PY%" -m uvicorn server:app --host 0.0.0.0 --port 8001"

REM ── Gateway v3: SwarmBus + all agents (NEXUS, ORACLE, FORGE, CODEX, SENTINEL)
echo Starting gateway+swarm:8002...
start "gateway" cmd /c "cd /d "%APP%backend" && "%PY%" -m uvicorn gateway_v3:app --host 0.0.0.0 --port 8002"

REM ── Frontend ──────────────────────────────────────────────────────────────
start "frontend" cmd /c "cd /d "%APP%" && "%PY%" -m http.server 3210 --directory frontend\build"

REM ── Voice listener (non-critical, failure is OK) ──────────────────────────
start "voice" cmd /c "cd /d "%APP%" && "%PY%" whisper_listener.py"

echo Done. Open http://localhost:3210
