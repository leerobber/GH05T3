@echo off
:: Sovereign Recall — Continuous Intelligence Capture
:: Runs as a background service on TatorTot.
:: Captures: Claude sessions, git diffs, files, browser, terminal
:: Output:   backend\data\training\sovereign_recall.jsonl
::
:: Run from anywhere. Starts automatically with run.bat.
:: To run standalone: native\windows\recall.bat

setlocal enabledelayedexpansion
cd /d "%~dp0..\.."
set APP=%CD%

echo.
echo  =============================================
echo   SOVEREIGN RECALL — CHRONICLE AGENT
echo   Mira Solis / Chief Data Intelligence
echo   Capturing all TatorTot intelligence...
echo  =============================================
echo.

:: ── Python check ──────────────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Run install.ps1 first.
    pause & exit /b 1
)

:: ── Dep check ─────────────────────────────────────────────────────────────────
python -c "import watchdog, httpx" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing Sovereign Recall dependencies...
    pip install watchdog httpx -q
    if errorlevel 1 ( echo [ERROR] Dep install failed & pause & exit /b 1 )
)

:: ── Config ────────────────────────────────────────────────────────────────────
set RECALL_WATCH_PATHS=%APP%
set RECALL_CLAUDE_DIR=%USERPROFILE%\.claude\projects
set RECALL_SCAN_INTERVAL=300
set RECALL_QUALITY_MIN=3
set RECALL_BROWSER=all
set RECALL_ENABLE_CLIP=1

echo [RECALL] Watch paths : %RECALL_WATCH_PATHS%
echo [RECALL] Claude dir  : %RECALL_CLAUDE_DIR%
echo [RECALL] Scan every  : %RECALL_SCAN_INTERVAL%s
echo [RECALL] Output      : %APP%\backend\data\training\sovereign_recall.jsonl
echo.

:: ── Run ───────────────────────────────────────────────────────────────────────
python backend\sovereign_recall.py
