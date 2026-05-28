@echo off
title SovereignNation — Private AI Platform
color 0B
setlocal

echo.
echo  ============================================================
echo   SOVEREIGNNATION  v2.0  --  Private AI Platform
echo  ============================================================
echo.

:: ── 1/4  Ollama ──────────────────────────────────────────────────────────────
tasklist /fi "imagename eq ollama.exe" | find "ollama.exe" >nul 2>&1
if errorlevel 1 (
    echo  [1/4] Starting Ollama...
    start /min "" ollama serve
) else (
    echo  [1/4] Ollama already running.
)

echo  [1/4] Waiting for Ollama API to be ready...
:wait_ollama
powershell -NonInteractive -Command ^
  "try{Invoke-RestMethod http://localhost:11434/api/tags -TimeoutSec 2|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto wait_ollama
)
echo  [1/4] Ollama is ready.
echo.

:: ── 2/4  Auto-updater (background, non-blocking) ────────────────────────────
echo  [2/4] Checking for agent updates (background)...
start /min "" python "%~dp0updater.py" --check
echo.

:: ── 3/4  Client UI ───────────────────────────────────────────────────────────
echo  [3/4] Starting Client UI server...
start /min "" python "%~dp0serve.py"

echo  [3/4] Waiting for Client UI to be ready...
:wait_serve
powershell -NonInteractive -Command ^
  "try{Invoke-RestMethod http://localhost:7861/health -TimeoutSec 2|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_serve
)
echo  [3/4] Client UI ready at http://localhost:7861
echo.

:: ── 4/4  Cloudflare Tunnel ───────────────────────────────────────────────────
echo  [4/4] Starting Cloudflare Tunnel...
echo.
echo  ============================================================
echo   Your public demo URL will appear below.
echo   Copy the https://*.trycloudflare.com link
echo   and paste it into your Zoom chat.
echo  ============================================================
echo.

:: Open local UI in browser
start "" http://localhost:7861

:: Launch tunnel — URL prints to console
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:7861

echo.
echo  Tunnel closed. Press any key to exit.
pause >nul
