@echo off
title SovereignNation — Full AI Stack
color 0B
setlocal EnableDelayedExpansion

set "PHIPY=C:\Users\leer4\phi_dml_env\Scripts\python.exe"
set "LOGDIR=%~dp0..\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo.
echo  ============================================================
echo   SOVEREIGNNATION  v3.0  --  Full AI Stack
echo   phi-3.5-mini ^| npu-embed ^| pipeline ^| ollama ^| tunnel
echo  ============================================================
echo.

:: ── Launch slow loaders immediately so they warm up in parallel ───────────────

curl -s --max-time 1 http://127.0.0.1:8112/health >nul 2>&1
if errorlevel 1 (
    echo  [2/6] Launching Phi-3.5-mini GPU service (port 8112)... ^(log: logs\phi.log^)
    start "Phi8112" /min cmd /c ""%PHIPY%" "%~dp0phi_service.py" > "%LOGDIR%\phi.log" 2>&1"
) else (
    echo  [2/6] Phi-3.5-mini already running.
)

curl -s --max-time 1 http://127.0.0.1:8111/health >nul 2>&1
if errorlevel 1 (
    echo  [3/6] Launching NPU Embedding + Whisper service (port 8111)...
    start /min "NPU8111" C:\Users\leer4\.conda\envs\ryzen-ai-1.7.0\python.exe "%~dp0npu_embedding_service.py"
) else (
    echo  [3/6] NPU Embedding already running.
)
echo.

:: ── 1/6  Ollama ──────────────────────────────────────────────────────────────
tasklist /fi "imagename eq ollama.exe" | find "ollama.exe" >nul 2>&1
if errorlevel 1 (
    echo  [1/6] Starting Ollama...
    start /min "" ollama serve
) else (
    echo  [1/6] Ollama already running.
)

echo  [1/6] Waiting for Ollama (port 11434)...
set /a _tries=0
:wait_ollama
set /a _tries+=1
if !_tries! GTR 30 (echo  [1/6] ERROR: Ollama timed out. & goto done)
curl -s --max-time 2 http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (timeout /t 2 /nobreak >nul & goto wait_ollama)
echo  [1/6] Ollama ready.
echo.

:: ── 2/6  Wait for Phi (ready:true — GPU model must finish loading) ────────────
echo  [2/6] Waiting for Phi-3.5-mini (CUDA model load ~7s)...
set /a _tries=0
:wait_phi
set /a _tries+=1
if !_tries! GTR 40 (echo  [2/6] WARNING: Phi timed out — /phi/chat unavailable. & goto skip_phi)
curl -s --max-time 3 http://127.0.0.1:8112/health 2>nul | python -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('ready') else 1)" >nul 2>&1
if errorlevel 1 (timeout /t 2 /nobreak >nul & goto wait_phi)
echo  [2/6] Phi-3.5-mini ready  (CUDA EP ~90 tok/s).
:skip_phi
echo.

:: ── 3/6  Wait for NPU embedding service ──────────────────────────────────────
echo  [3/6] Waiting for NPU Embedding service (Whisper + minilm)...
set /a _tries=0
:wait_npu
set /a _tries+=1
if !_tries! GTR 60 (echo  [3/6] WARNING: NPU service timed out — intent routing degraded. & goto skip_npu)
curl -s --max-time 3 http://127.0.0.1:8111/health >nul 2>&1
if errorlevel 1 (timeout /t 2 /nobreak >nul & goto wait_npu)
echo  [3/6] NPU Embedding service ready.
:skip_npu
echo.

:: ── 4/6  Client UI (serve.py, port 7861) ─────────────────────────────────────
curl -s --max-time 1 http://localhost:7861/health >nul 2>&1
if errorlevel 1 (
    echo  [4/6] Starting Client UI (port 7861)...
    start /min "Serve7861" python "%~dp0serve.py"
) else (
    echo  [4/6] Client UI already running.
)
echo.

:: ── 5/6  Pipeline Backend — main AI brain (port 8099) ────────────────────────
curl -s --max-time 1 http://localhost:8099/health >nul 2>&1
if errorlevel 1 (
    echo  [5/6] Starting Pipeline Backend (port 8099)...
    start /min "Pipeline8099" python "%~dp0pipeline_backend.py"
) else (
    echo  [5/6] Pipeline Backend already running.
)

echo  [5/6] Waiting for Pipeline Backend...
set /a _tries=0
:wait_pipe
set /a _tries+=1
if !_tries! GTR 20 (echo  [5/6] ERROR: Pipeline failed to start. & goto done)
curl -s --max-time 3 http://localhost:8099/health >nul 2>&1
if errorlevel 1 (timeout /t 1 /nobreak >nul & goto wait_pipe)
echo  [5/6] Pipeline Backend ready.
echo.

:: ── 6/6  Auto-updater (background) ───────────────────────────────────────────
echo  [6/6] Checking for agent updates (background)...
start /min "" python "%~dp0updater.py" --check
echo.

:: Open agent console in browser
start "" http://localhost:8099/console

:: ── Cloudflare Tunnel → agent console ────────────────────────────────────────
echo  ============================================================
echo   Full stack loaded.
echo   LOCAL:  http://localhost:8099/console
echo   PUBLIC: https://*.trycloudflare.com  (URL appears below)
echo  ============================================================
echo.

"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:8099

:done
echo.
echo  Press any key to exit.
pause >nul
