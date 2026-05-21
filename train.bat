@echo off
REM ============================================================
REM  SOVEREIGN TRAINING PIPELINE ? Single entry point
REM
REM  USAGE:
REM    train.bat                      preflight + RunPod ORPO (Avery)
REM    train.bat [mode]               sft / dpo / orpo / grpo  (Avery)
REM    train.bat [agent]              forge / oracle / codex / sentinel / nexus
REM    train.bat [agent] [mode]       forge orpo
REM    train.bat all                  train all 6 agents combined
REM    train.bat all [mode]           all grpo
REM    train.bat bootstrap            generate training data for all agents
REM    train.bat bootstrap [agent]    generate data for one agent
REM    train.bat status               check running pod
REM    train.bat stop                 stop running pod
REM    train.bat cleanup              stop ALL running pods
REM    train.bat tail                 attach to live training log
REM    train.bat deploy               merge LoRA + GGUF + reload Ollama
REM    train.bat check                preflight dry-run (no upload)
REM ============================================================

REM -- Find Python with datasets installed ----------------------------------
REM  datasets lives in system Python, not the project venv.
REM  Always prefer system Python for HF/datasets operations.
set SYS_PYTHON=C:\Users\leer4\AppData\Local\Programs\Python\Python312\python.exe
set VENV_PYTHON=%~dp0.venv\Scripts\python.exe

REM -- Verify datasets is available in system Python (canonical location) ---
"%SYS_PYTHON%" -c "import datasets" 2>nul
if errorlevel 1 (
    echo ERROR: datasets not in system Python. Run:
    echo   "%SYS_PYTHON%" -m pip install datasets huggingface_hub
    exit /b 1
)
set PYTHON=%SYS_PYTHON%

REM -- Parse arguments ------------------------------------------------------
set ARG1=%~1
set ARG2=%~2
if "%ARG1%"=="" set ARG1=orpo

REM ?? Commands that don't need preflight ??
if "%ARG1%"=="status"    goto :status
if "%ARG1%"=="stop"      goto :stop
if "%ARG1%"=="cleanup"   goto :cleanup
if "%ARG1%"=="tail"      goto :tail
if "%ARG1%"=="deploy"    goto :deploy
if "%ARG1%"=="check"     goto :check
if "%ARG1%"=="bootstrap" goto :bootstrap

REM ?? Determine AGENT and MODE ??
REM  Agent names
set IS_AGENT=0
if "%ARG1%"=="avery"    set IS_AGENT=1
if "%ARG1%"=="forge"    set IS_AGENT=1
if "%ARG1%"=="oracle"   set IS_AGENT=1
if "%ARG1%"=="codex"    set IS_AGENT=1
if "%ARG1%"=="sentinel" set IS_AGENT=1
if "%ARG1%"=="nexus"    set IS_AGENT=1
if "%ARG1%"=="all"      set IS_AGENT=1

if "%IS_AGENT%"=="1" (
    set TRAIN_AGENT=%ARG1%
    if "%ARG2%"=="" (
        set TRAIN_MODE=orpo
    ) else (
        set TRAIN_MODE=%ARG2%
    )
) else (
    REM ARG1 is a mode
    set TRAIN_AGENT=avery
    set TRAIN_MODE=%ARG1%
)

REM ?? Determine split based on agent ??
if "%TRAIN_AGENT%"=="avery" (
    set TRAIN_SPLIT=bootstrap_dpo
) else (
    set TRAIN_SPLIT=
)

echo.
echo +=====================================================+
echo ^|  SOVEREIGN TRAINING PIPELINE                       ^|
echo +=====================================================+
echo   Agent : %TRAIN_AGENT%
echo   Mode  : %TRAIN_MODE%
if not "%TRAIN_SPLIT%"=="" echo   Split : %TRAIN_SPLIT%
echo.

REM -- STEP 1: Preflight ----------------------------------------------------
echo [STEP 1/3] Pre-flight checks + HF upload...
"%PYTHON%" pre_train.py
if errorlevel 1 (
    echo.
    echo ERROR: Pre-flight failed. Fix the issues above and re-run.
    pause
    exit /b 1
)
echo.

REM -- STEP 2: Launch RunPod training ----------------------------------------
echo [STEP 2/3] Launching RunPod training (agent=%TRAIN_AGENT%  mode=%TRAIN_MODE%)...
echo   (Ctrl+C is safe ? pod keeps running. Resume with: train.bat tail)
echo.
if "%TRAIN_SPLIT%"=="" (
    "%PYTHON%" runpod_launcher.py --mode %TRAIN_MODE%
) else (
    "%PYTHON%" runpod_launcher.py --mode %TRAIN_MODE% --split %TRAIN_SPLIT%
)
if errorlevel 1 (
    echo.
    echo Launcher exited with error. Check: train.bat status
    pause
    exit /b 1
)
echo.

REM -- STEP 3: Deploy prompt -------------------------------------------------
echo [STEP 3/3] Training complete.
echo.
choice /C YN /M "Deploy LoRA to local Ollama now?"
if errorlevel 2 goto :end
goto :deploy

REM ==========================================================================
:bootstrap
REM Generate training data for agents using Claude API
echo.
echo +=====================================================+
echo ^|  AGENT BOOTSTRAP DATA GENERATOR                    ^|
echo +=====================================================+
if "%ARG2%"=="" (
    echo   Generating data for ALL 6 agents...
    "%PYTHON%" agents_bootstrap.py
) else (
    echo   Generating data for agent: %ARG2%
    "%PYTHON%" agents_bootstrap.py --agent %ARG2%
)
if errorlevel 1 (
    echo ERROR: Bootstrap failed.
    pause
    exit /b 1
)
echo.
echo Data generated. Run pre_train.py to upload to HuggingFace:
echo   train.bat check
goto :end

:status
echo.
"%PYTHON%" runpod_launcher.py --status
goto :end

:stop
echo.
"%PYTHON%" runpod_launcher.py --stop
goto :end

:cleanup
echo.
"%PYTHON%" runpod_launcher.py --cleanup
goto :end

:tail
echo.
"%PYTHON%" runpod_launcher.py --tail
goto :end

:check
echo.
echo Running pre-flight dry-run (no uploads)...
"%PYTHON%" pre_train.py --dry-run
goto :end

:deploy
echo.
echo Deploying LoRA to local Ollama...
"%PYTHON%" merge_and_convert.py
goto :end

:end
echo.
echo Done.
