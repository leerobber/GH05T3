@echo off
REM GH05T3 v3 - launcher. Double-click or run from repo root.
REM Backend + gateway bind to 0.0.0.0 so Android on same WiFi can reach the dashboard.
setlocal enableextensions

set APP=%~dp0
cd /d "%APP%"

REM Ensure runtime dirs exist
if not exist "%APP%mongo-data"        mkdir "%APP%mongo-data"
if not exist "%APP%backend\memory"    mkdir "%APP%backend\memory"
if not exist "%APP%backend\evolution" mkdir "%APP%backend\evolution"

set PY=%APP%backend\.venv\Scripts\python

REM Read IPs saved by install.ps1
set LAN_IP=localhost
set REMOTE_IP=localhost
if exist "%APP%lan_ip.txt"    set /p LAN_IP=<"%APP%lan_ip.txt"
if exist "%APP%remote_ip.txt" set /p REMOTE_IP=<"%APP%remote_ip.txt"

REM ---- Locate mongod (winget may not update PATH in current session) ----
where mongod >nul 2>&1
if not errorlevel 1 goto mongod_ok

for /d %%v in ("C:\Program Files\MongoDB\Server\*") do set MONGOBIN=%%v\bin
if not defined MONGOBIN goto mongod_missing
set "PATH=%PATH%;%MONGOBIN%"
goto mongod_ok

:mongod_missing
echo ERROR: mongod not found. Re-run install.ps1 as Administrator.
pause
exit /b 1

:mongod_ok
REM ---- Prevent sleep / screen-off while GH05T3 is running (critical for remote access) ----
powercfg /setactive SCHEME_MIN >nul 2>&1
powercfg /change standby-timeout-ac 0 >nul 2>&1
powercfg /change standby-timeout-dc 0 >nul 2>&1
powercfg /change hibernate-timeout-ac 0 >nul 2>&1
powercfg /change hibernate-timeout-dc 0 >nul 2>&1

REM ---- MongoDB :27017  -  cache capped at 512 MB (default is 50%% RAM) ----
start "gh05t3-mongo" /min mongod --dbpath "%APP%mongo-data" --bind_ip 127.0.0.1 --port 27017 --quiet --wiredTigerCacheSizeGB 0.5

REM Wait up to ~12s for MongoDB to accept connections before starting the backend.
:mongo_wait
timeout /t 2 /nobreak > nul
mongosh --quiet --eval "db.runCommand({ping:1})" mongodb://127.0.0.1:27017 >nul 2>&1
if errorlevel 1 (
    echo Waiting for MongoDB...
    timeout /t 2 /nobreak > nul
    mongosh --quiet --eval "db.runCommand({ping:1})" mongodb://127.0.0.1:27017 >nul 2>&1
)
timeout /t 2 /nobreak > nul

REM ---- Tuning #5: ABOVENORMAL priority keeps GH05T3 responsive under load ----
REM ---- server.py :8001 ----
start "gh05t3-backend" /min /ABOVENORMAL /d "%APP%backend" "%PY%" -m uvicorn server:app --host 0.0.0.0 --port 8001

REM ---- gateway_v3 :8002 (includes MCP server at /mcp/sse) ----
start "gh05t3-gateway-v3" /min /ABOVENORMAL /d "%APP%backend" "%PY%" -m uvicorn gateway_v3:app --host 0.0.0.0 --port 8002

REM ---- Frontend static bundle :3210 ----
start "gh05t3-frontend" /min "%PY%" -m http.server 3210 --directory "%APP%frontend\build"

REM ---- Whisper listener ----
start "gh05t3-whisper" /min "%PY%" "%APP%whisper_listener.py"

echo.
echo  GH05T3 is starting...
echo.
echo   Dashboard  (this PC):   http://localhost:3210
echo   Dashboard  (remote):    http://%REMOTE_IP%:3210
echo.
echo   Backend API:            http://%REMOTE_IP%:8001
echo   Gateway v3 + MCP:       http://%REMOTE_IP%:8002
echo   MCP SSE endpoint:       http://%REMOTE_IP%:8002/mcp/sse
echo   MCP info + config:      http://%REMOTE_IP%:8002/mcp/info
echo   Peer mesh:              http://%REMOTE_IP%:8002/peers
echo.
if exist "%APP%tailscale_ip.txt" (
    echo   Tailscale ACTIVE  -  Claude Code + Android reach GH05T3 from ANYWHERE
    echo   Sleep is DISABLED  -  laptop stays awake for remote access
) else (
    echo   LAN only  -  Install Tailscale for remote Claude Code access.
    echo   https://tailscale.com/download
)
echo.
echo   Claude Code MCP config:  http://%REMOTE_IP%:8002/mcp/info
echo   Paste your keys in the LLM Config panel on first open.
echo   Free Groq key:  https://console.groq.com
echo.

REM ---- Tray icon (keeps this window alive as the host process) ----
"%PY%" "%APP%tray.py"

endlocal
