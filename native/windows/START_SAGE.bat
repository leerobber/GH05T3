@echo off
title Aethyro SAGE Engine
color 0A
setlocal

set APP=C:\Users\leer4\GH05T3
set PY=python

echo.
echo  ============================================================
echo   AETHYRO SAGE/KAIROS SELF-IMPROVEMENT ENGINE
echo   Port 8098  -  Honcho Dashboard API
echo  ============================================================
echo.

REM Kill any existing sage engine on 8098
for /f "tokens=5" %%A in ('netstat -ano 2^>nul ^| findstr "0.0.0.0:8098 "') do (
    if not "%%A"=="0" taskkill /F /PID %%A >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo  Starting SAGE Engine on port 8098...
cd /d "%APP%"
set PYTHONIOENCODING=utf-8
start "SAGE-Engine" /min "%PY%" -m uvicorn start_sage:app --host 0.0.0.0 --port 8098 --log-level warning

echo  Waiting for SAGE Engine to come online...
:WAIT_SAGE
powershell -NonInteractive -Command "try{Invoke-RestMethod http://localhost:8098/health -TimeoutSec 2|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 ( timeout /t 2 /nobreak >nul & goto WAIT_SAGE )

echo  [OK] SAGE Engine online.
echo.
echo  ============================================================
echo   Honcho Status:     http://localhost:8098/status
echo   SAGE Status:       http://localhost:8098/sage/status
echo   SAGE Trigger:      POST http://localhost:8098/sage/run
echo   KAIROS Plans:      http://localhost:8098/kairos/plans
echo   Memory Stats:      http://localhost:8098/memory/stats
echo   Iron Dome Verify:  http://localhost:8098/iron_dome/verify
echo   IBAC Policy:       http://localhost:8098/ibac/policy
echo   Honcho WS:         ws://localhost:8098/ws
echo  ============================================================
echo.
echo  SAGE runs nightly at 3:00 AM automatically.
echo  Use POST /sage/run to trigger a manual cycle.
echo.
pause
