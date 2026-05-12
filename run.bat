@echo off
setlocal enableextensions
set APP=%~dp0
cd /d "%APP%"

echo GH05T3 launching...

REM Always use system python or venv
set PY=python
where python >nul 2>&1 || (
    if exist backend\.venv\Scripts\python.exe (
        set PY=backend\.venv\Scripts\python.exe
    )
)

start "mongo" mongod --dbpath "%APP%mongo-data" --port 27017 --bind_ip 127.0.0.1

timeout /t 3 >nul

start "gh05t3-model" cmd /c "cd /d "%APP%backend" && %PY% gh05t3_inference.py"
start "backend" cmd /c "cd /d "%APP%backend" && %PY% -m uvicorn server:app --host 0.0.0.0 --port 8001"
start "gateway" cmd /c "cd /d "%APP%backend" && %PY% -m uvicorn gateway_v3:app --host 0.0.0.0 --port 8002"
start "frontend" cmd /c "%PY% -m http.server 3210 --directory frontend\build"
start "voice" cmd /c "%PY% whisper_listener.py"

echo GH05T3 running...
pause
