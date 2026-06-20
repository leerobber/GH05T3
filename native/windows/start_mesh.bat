@echo off
setlocal
set AETHYRO_SKIP_LICENSE=1
set APP=%~dp0..\..
cd /d "%APP%\backend"
set PY=%APP%\backend\.venv\Scripts\python.exe

powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://localhost:8001/api/health' -TimeoutSec 2).StatusCode } catch { 0 }" | findstr 200 >nul
if errorlevel 1 (
  echo Starting GH05T3 backend :8001 ...
  start "gh05t3-backend" /MIN "%PY%" -m uvicorn server:app --host 0.0.0.0 --port 8001
)

powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://localhost:8002/health' -TimeoutSec 2).StatusCode } catch { 0 }" | findstr 200 >nul
if errorlevel 1 (
  echo Starting GH05T3 gateway :8002 ...
  start "gh05t3-gateway" /MIN "%PY%" -m uvicorn gateway_v3:app --host 0.0.0.0 --port 8002
)

echo GH05T3 mesh processes launched. Check http://localhost:8002/health in ~15s.
endlocal