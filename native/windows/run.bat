@echo off
REM GH05T3 — daily launcher. Double-click or auto-run on Windows login.
setlocal enableextensions

set APP=%~dp0
cd /d "%APP%"

REM Ensure MongoDB data dir exists
if not exist "%APP%mongo-data" mkdir "%APP%mongo-data"

REM Start MongoDB in background (pipe logs, suppress window)
start "gh05t3-mongo" /min cmd /c "mongod --dbpath "%APP%mongo-data" --bind_ip 127.0.0.1 --port 27017 --quiet"

REM Give Mongo a moment
timeout /t 2 /nobreak > nul

REM Start backend (FastAPI via uvicorn)
start "gh05t3-backend" /min cmd /c "%APP%backend\.venv\Scripts\python -m uvicorn server:app --host 127.0.0.1 --port 8001 --app-dir "%APP%backend""

REM Serve prebuilt frontend on 3210 (pure python http.server, no node needed at runtime)
start "gh05t3-frontend" /min cmd /c "%APP%backend\.venv\Scripts\python -m http.server 3210 --directory "%APP%frontend\build""

REM Whisper listener — speaks stuck-alerts / elite proposals via edge-tts
start "gh05t3-whisper" /min cmd /c "%APP%backend\.venv\Scripts\python "%APP%whisper_listener.py""

REM Tray icon + auto-opens dashboard; blocks so this terminal is the host
"%APP%backend\.venv\Scripts\python" "%APP%tray.py"

endlocal
