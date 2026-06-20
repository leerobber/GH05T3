@echo off
REM GH05T3 gateway_v3 — port 8002
setlocal
cd /d "%~dp0..\.."
if not defined AETHYRO_SKIP_LICENSE set AETHYRO_SKIP_LICENSE=1

powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8002/health' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>&1
if %ERRORLEVEL%==0 (
    echo Gateway already running on http://localhost:8002
    echo Do not start a second instance — port 8002 is in use.
    echo To restart: stop the existing process first, then run this script again.
    exit /b 0
)

cd backend
echo Starting gateway_v3 on http://localhost:8002 ...
".venv\Scripts\python.exe" -m uvicorn gateway_v3:app --host 0.0.0.0 --port 8002
exit /b %ERRORLEVEL%