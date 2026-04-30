@echo off
REM GH05T3 v3 — launcher. Double-click or auto-run on Windows login.
setlocal enableextensions

set APP=%~dp0
cd /d "%APP%"

REM Ensure data dirs exist
if not exist "%APP%mongo-data"            mkdir "%APP%mongo-data"
if not exist "%APP%backend\memory"        mkdir "%APP%backend\memory"
if not exist "%APP%backend\evolution"     mkdir "%APP%backend\evolution"

REM ── MongoDB ──────────────────────────────────────────────────────────────
start "gh05t3-mongo" /min cmd /c ^
  "mongod --dbpath "%APP%mongo-data" --bind_ip 127.0.0.1 --port 27017 --quiet"

timeout /t 2 /nobreak > nul

REM ── Backend — server.py (port 8001, existing FastAPI + MongoDB) ──────────
start "gh05t3-backend" /min cmd /c ^
  ""%APP%backend\.venv\Scripts\python" -m uvicorn server:app ^
   --host 127.0.0.1 --port 8001 --app-dir "%APP%backend""

REM ── Gateway v3 — SwarmBus + Claude + GitHub (port 8002) ─────────────────
start "gh05t3-gateway-v3" /min cmd /c ^
  "cd /d "%APP%backend" && ^
   "%APP%backend\.venv\Scripts\python" -m uvicorn gateway_v3:app ^
   --host 127.0.0.1 --port 8002"

REM ── Frontend — prebuilt static bundle (port 3210) ────────────────────────
start "gh05t3-frontend" /min cmd /c ^
  ""%APP%backend\.venv\Scripts\python" -m http.server 3210 ^
   --directory "%APP%frontend\build""

REM ── Whisper listener ─────────────────────────────────────────────────────
start "gh05t3-whisper" /min cmd /c ^
  ""%APP%backend\.venv\Scripts\python" "%APP%whisper_listener.py""

REM ── Tray icon (blocks — keeps this window as host) ───────────────────────
"%APP%backend\.venv\Scripts\python" "%APP%tray.py"

endlocal
