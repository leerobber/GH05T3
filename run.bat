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
if exist "%APP%venv\Scripts\python.exe" (
    set PY=%APP%venv\Scripts\python.exe
) else if exist "%APP%backend\.venv\Scripts\python.exe" (
    set PY=%APP%backend\.venv\Scripts\python.exe
)

REM ── Security: check API token ─────────────────────────────────────────────
set GH05T3_API_TOKEN=
if exist "%APP%backend\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%APP%backend\.env") do (
        if /i "%%A"=="GH05T3_API_TOKEN" set GH05T3_API_TOKEN=%%B
    )
)
if "%GH05T3_API_TOKEN%"=="" (
    echo.
    echo   [SECURITY WARNING] GH05T3_API_TOKEN not set in backend\.env
    echo   Gateway is running in OPEN MODE - anyone on LAN can call the API.
    echo   To secure: add GH05T3_API_TOKEN=^<random-32-char-token^> to backend\.env
    echo.
)

REM ── Tailscale: auto-detect IP and export for gateway ──────────────────────
set TAILSCALE_OWN_IP=
for /f "tokens=*" %%I in ('tailscale ip --4 2^>nul') do set TAILSCALE_OWN_IP=%%I
if defined TAILSCALE_OWN_IP (
    set REMOTE_IP=%TAILSCALE_OWN_IP%
    echo   [TAILSCALE] Active - IP: %TAILSCALE_OWN_IP%
) else (
    REM Fall back to first 192.168.x.x LAN address for display
    for /f "tokens=2 delims=:" %%I in ('ipconfig ^| findstr /i "IPv4.*192\.168\."') do (
        for /f "tokens=* delims= " %%J in ("%%I") do set REMOTE_IP=%%J
    )
    if not defined REMOTE_IP set REMOTE_IP=localhost
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
start "gateway" cmd /c "cd /d "%APP%backend" && set TAILSCALE_OWN_IP=%TAILSCALE_OWN_IP% && "%PY%" -m uvicorn gateway_v3:app --host 0.0.0.0 --port 8002"

REM ── Frontend ──────────────────────────────────────────────────────────────
start "frontend" cmd /c "cd /d "%APP%" && "%PY%" -m http.server 3210 --directory frontend\build"

REM ── Voice listener (non-critical, failure is OK) ──────────────────────────
start "voice" cmd /c "cd /d "%APP%" && "%PY%" whisper_listener.py"

REM ── Training ops tools (set ENABLE_OPS=1 in environment or .env to activate)
set ENABLE_OPS=
if exist "%APP%backend\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%APP%backend\.env") do (
        if /i "%%A"=="ENABLE_OPS" set ENABLE_OPS=%%B
    )
)
if "%ENABLE_OPS%"=="1" (
    echo Starting training ops tools ^(herald + cmd-listener^)...
    start "herald" cmd /c "cd /d "%APP%" && "%PY%" herald.py --console"
    start "cmd-listener" cmd /c "cd /d "%APP%" && "%PY%" cmd_listener.py"
)

echo.
echo   Dashboard  : http://localhost:3210
echo   Remote     : http://%REMOTE_IP%:3210
echo   Gateway    : http://%REMOTE_IP%:8002
echo   Mesh peers : http://%REMOTE_IP%:8002/peers
echo   MCP (SSE)  : http://%REMOTE_IP%:8002/mcp/sse
echo.
if "%GH05T3_API_TOKEN%"=="" (
    echo   [!] OPEN MODE - set GH05T3_API_TOKEN in backend\.env to secure
) else (
    echo   [OK] API token set - gateway is authenticated
)
if defined TAILSCALE_OWN_IP (
    echo   [OK] Tailscale active - reachable from anywhere at %TAILSCALE_OWN_IP%
) else (
    echo   [!] Tailscale not detected - LAN access only
)
echo.
echo   Training ops: set ENABLE_OPS=1 in backend\.env to auto-start herald+cmd-listener
echo.
echo Done.

REM ── Open dashboard in browser after services start ────────────────────────
timeout /t 5 >nul
start "" "http://localhost:3210"
