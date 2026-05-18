@echo off
setlocal enableextensions
set APP=C:\Users\leer4\GH05T3
set ECO=C:\Users\leer4\Documents\agent-economy
cd /d "%APP%"

echo === GH05T3 + Sovereign Economy ===

REM ── Kill any leftover processes on all ports ──────────────────────────────
echo Clearing ports 8001 8002 3210 8081...
for %%P in (8001 8002 3210 8081) do (
    for /f "tokens=5" %%A in ('netstat -ano 2^>nul ^| findstr "0.0.0.0:%%P "') do (
        if not "%%A"=="0" taskkill /F /PID %%A >nul 2>&1
    )
)
timeout /t 2 >nul

REM ── Python executables ────────────────────────────────────────────────────
set PY=%APP%\backend\.venv\Scripts\python.exe
if not exist "%PY%" set PY=python

set ECO_PY=%ECO%\venv\Scripts\python.exe
if not exist "%ECO_PY%" set ECO_PY=python

REM ── Ollama ────────────────────────────────────────────────────────────────
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul 2>&1
if errorlevel 1 (
    echo Starting Ollama...
    start "ollama" /min ollama serve
    timeout /t 4 >nul
)

REM ── Economy API: must start first (GH05T3 sends credits to it) ───────────
echo Starting Economy API (8081)...
start "economy-api" /min cmd /c "cd /d "%ECO%" && "%ECO_PY%" start.py"

REM Wait up to 20s for economy API to answer
echo Waiting for Economy API...
set /a _w=0
:WAIT_ECO
timeout /t 2 /nobreak >nul
curl -s -o nul http://localhost:8081/system/stats
if not errorlevel 1 goto ECO_UP
set /a _w+=1
if %_w% lss 10 goto WAIT_ECO
echo WARNING: Economy API did not respond in 20s — continuing anyway
goto AFTER_ECO
:ECO_UP
echo Economy API is UP.
:AFTER_ECO

REM ── Economy Auto-Runner (runs economy ticks) ──────────────────────────────
echo Starting Auto-Runner...
start "auto-runner" /min cmd /c "cd /d "%ECO%" && "%ECO_PY%" auto_runner.py --batch 10 --interval 0.5 --export-every 50"

REM ── MongoDB ───────────────────────────────────────────────────────────────
echo Starting MongoDB...
if not exist "%APP%\mongo-data" mkdir "%APP%\mongo-data"
start "mongo" mongod --dbpath "%APP%\mongo-data" --port 27017 --bind_ip 127.0.0.1
timeout /t 3 >nul

REM ── Backend (server.py — economy context, CFO, APScheduler, Telegram) ────
echo Starting backend (8001)...
start "backend" cmd /c "cd /d "%APP%\backend" && "%PY%" -m uvicorn server:app --host 0.0.0.0 --port 8001"

REM ── Gateway v3 (SwarmBus — NEXUS, ORACLE, FORGE, CODEX, SENTINEL) ────────
echo Starting gateway+swarm (8002)...
start "gateway" cmd /c "cd /d "%APP%\backend" && "%PY%" -m uvicorn gateway_v3:app --host 0.0.0.0 --port 8002"

REM ── Frontend ──────────────────────────────────────────────────────────────
start "frontend" cmd /c "cd /d "%APP%" && "%PY%" -m http.server 3210 --directory frontend\build"

REM ── Voice (non-critical) ──────────────────────────────────────────────────
start "voice" /min cmd /c "cd /d "%APP%" && "%PY%" whisper_listener.py"

echo.
echo === ALL SYSTEMS RUNNING ===
echo   GH05T3:        http://localhost:3210
echo   Backend API:   http://localhost:8001/docs
echo   Gateway+NEXUS: http://localhost:8002/docs
echo   Economy API:   http://localhost:8081/docs
echo ===========================
echo.
echo Close this window to keep services running in background.
