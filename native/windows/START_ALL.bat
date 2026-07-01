@echo off
title GH05T3 — System Launcher
color 0B
setlocal

set APP=C:\Users\leer4\GH05T3
set PY=%APP%\backend\.venv\Scripts\python.exe
if not exist "%PY%" set PY=python

echo.
echo  ============================================================
echo   GH05T3 + SOVEREIGN ECONOMY — SYSTEM LAUNCHER
echo  ============================================================
echo.

REM ── 1. Ollama (prerequisite for all AI calls) ─────────────────────────────
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul 2>&1
if errorlevel 1 (
    echo  [1] Starting Ollama...
    start "ollama" /min ollama serve
) else (
    echo  [1] Ollama already running.
)

echo  [1] Waiting for Ollama API...
:WAIT_OLLAMA
curl -sf --max-time 2 http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 ( timeout /t 2 /nobreak >nul & goto WAIT_OLLAMA )
echo  [1] Ollama ready.
echo.

REM ── 2. Kill any stale services on managed ports ─────────────────────────
for %%P in (8090 8002 8001 8081 8099) do (
    for /f "tokens=5" %%A in ('netstat -ano 2^>nul ^| findstr "0.0.0.0:%%P "') do (
        if not "%%A"=="0" taskkill /F /PID %%A >nul 2>&1
    )
)
timeout /t 1 /nobreak >nul

REM ── 3. Launch supervisor (manages all 9 services with auto-restart) ───────
echo  [2] Starting Supervisor (manages all services + auto-restart)...
start "GH05T3-Supervisor" /min "%PY%" "%APP%\scripts\runtime\supervisor.py"
timeout /t 5 /nobreak >nul

REM ── 4. Wait for supervisor status API ───────────────────────────────────
echo  [2] Waiting for supervisor to come online...
:WAIT_SUP
curl -sf --max-time 2 http://localhost:8090/status >nul 2>&1
if errorlevel 1 ( timeout /t 2 /nobreak >nul & goto WAIT_SUP )
echo  [2] Supervisor online.
echo.

REM ── 5. Print status ──────────────────────────────────────────────────────
"%PY%" "%APP%\scripts\runtime\supervisor.py" --status

echo.
echo  ============================================================
echo   GH05T3:          http://localhost:3210
echo   Backend API:     http://localhost:8001/docs
echo   Gateway+NEXUS:   http://localhost:8002/docs
echo   Economy API:     http://localhost:8081/docs
echo   Supervisor:      http://localhost:8090/status
echo   SAGE Engine:     http://localhost:8098/health
echo   Sovereign IFace: http://localhost:8100/health
echo   Genome Lab UI:   http://localhost:7720/genome_dashboard.html
echo   Honcho Dash:     http://localhost:8098/status
echo   IBAC Daemon:     http://localhost:8098/ibac/policy
echo  ============================================================
echo.
echo  Supervisor runs in background with auto-restart.
echo  Close this window safely — services keep running.
echo.
pause
