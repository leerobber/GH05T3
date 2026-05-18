@echo off
title GH05T3 Launcher
cd /d "%~dp0"

echo.
echo  =====================================
echo   GH05T3 ^| Starting all services...
echo  =====================================
echo.

REM -- Python interpreter (backend venv has all deps)
set PY="%~dp0backend\.venv\Scripts\python.exe"

REM -- 1. MongoDB
echo [1/5] MongoDB...
start "GH05T3-mongo" /MIN cmd /c "mongod --dbpath "%~dp0mongo-data" --port 27017 --bind_ip 127.0.0.1"
timeout /t 2 /nobreak >nul

REM -- 2. Backend (server.py) on port 8001
echo [2/5] Backend (port 8001)...
start "GH05T3-backend" /MIN cmd /c "%PY% "%~dp0launch_backend.py""

REM -- 3. Gateway (gateway_v3.py) on port 8003
echo [3/5] Gateway (port 8003)...
start "GH05T3-gateway" /MIN cmd /c "%PY% "%~dp0launch_gateway.py""

REM -- 4. Frontend server (no-cache headers) on port 3210
echo [4/5] Frontend (port 3210)...
start "GH05T3-frontend" /MIN cmd /c "%PY% "%~dp0serve_frontend.py""

REM -- 5. Wait for backend to be ready then open Edge
echo [5/5] Waiting for backend...
timeout /t 4 /nobreak >nul

echo.
echo  Opening GH05T3 in Microsoft Edge...
start msedge "http://localhost:3210"

echo.
echo  =====================================
echo   GH05T3 running!
echo   Dashboard  ^>  http://localhost:3210
echo   Backend    ^>  http://localhost:8001
echo   Gateway    ^>  http://localhost:8003
echo  =====================================
echo.
echo  Close this window to keep services running in background.
echo  To stop everything, close the GH05T3-* terminal windows.
pause
