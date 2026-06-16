@echo off
:: GH05T3 — Train ALL 7 sovereign agent adapters sequentially
::
:: Runs overnight on RTX 5050 (~20 min/agent with Unsloth = ~2.5 hrs | ~45 min without = ~5-6 hrs).
:: Each agent trains on its domain-specific data PLUS SAGE elite proposals
:: from kairos_log.jsonl (exported by sft_export.py automatically).
::
:: Usage:
::   train_all_agents.bat                    -- all 7 agents, 500 steps each
::   train_all_agents.bat 200                -- 200 steps (faster, less quality)
::   train_all_agents.bat 500 codex-sovereign sentinel-sovereign  -- subset
::
:: First: run at least 350 SAGE cycles with rotation to get 50+ elites per agent.
::   python run_sage_cycles.py 350
::   python -m evolution.sft_export          (writes sft_data_*.jsonl)
::
:: Output: backend\models\<agent>_lora_adapter\ for each agent

setlocal enabledelayedexpansion
cd /d "%~dp0..\.."
set APP=%CD%

set STEPS=500
if not "%~1"=="" set STEPS=%~1

:: Default agent list (all 7 sovereign models)
set AGENTS=gh05t3-sovereign avery-sovereign codex-sovereign oracle-sovereign nexus-sovereign forge-sovereign sentinel-sovereign

:: If extra args given, use them as agent list
if not "%~2"=="" (
    set AGENTS=
    for %%A in (%*) do (
        if not "%%A"=="%STEPS%" set AGENTS=!AGENTS! %%A
    )
)

echo.
echo  ================================================================
echo   GH05T3 Sovereign Agent Training — All Agents
echo   Steps : %STEPS% per agent
echo   GPU   : RTX 5050  (Blackwell, CUDA 12.8)
echo   Agents: %AGENTS%
echo  ================================================================
echo.

:: ── Pre-export SAGE SFT data ──────────────────────────────────────────────────
echo [STEP 0] Exporting SAGE elite proposals per agent...
python -m evolution.sft_export >nul 2>&1
python -c "from evolution.sft_export import export_per_agent; r=export_per_agent(); print('  Per-agent export:', r)"
echo.

:: ── Python/CUDA check ────────────────────────────────────────────────────────
python -c "import torch, bitsandbytes; assert torch.cuda.is_available()" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing training stack for Blackwell RTX 5050...
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 -q
    pip install "transformers>=4.40.2" "peft>=0.10.0" "trl>=0.8.6" "accelerate>=0.29.3" ^
                "datasets>=2.19.0" "huggingface_hub>=0.22.0" "bitsandbytes>=0.44.0" -q
    echo [SETUP] Done.
    echo.
)

:: ── Unsloth check (2-3x speedup) ─────────────────────────────────────────────
python -c "import unsloth" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing Unsloth for 2-3x training speedup on Blackwell...
    pip install unsloth -q
    if errorlevel 1 (
        echo [WARN] Unsloth install failed — all agents will train at baseline speed
    ) else (
        echo [SETUP] Unsloth installed. Training will be 2-3x faster.
    )
    echo.
) else (
    echo [OK] Unsloth detected — fast path active for all agents
    echo.
)

:: ── Track results ────────────────────────────────────────────────────────────
set PASS_COUNT=0
set FAIL_COUNT=0
set FAILED_AGENTS=

:: ── Train each agent ─────────────────────────────────────────────────────────
set AGENT_NUM=0
for %%A in (%AGENTS%) do (
    set /a AGENT_NUM+=1
    echo.
    echo  ================================================================
    echo   Agent !AGENT_NUM! / %%A   [steps=%STEPS%]
    echo  ================================================================
    echo.

    python backend\training\train_local.py --agent %%A --steps %STEPS%
    set EXIT_CODE=!ERRORLEVEL!

    if !EXIT_CODE! equ 0 (
        echo   [OK] %%A adapter saved.
        set /a PASS_COUNT+=1
    ) else (
        echo   [FAIL] %%A training failed (exit !EXIT_CODE!)
        set /a FAIL_COUNT+=1
        set FAILED_AGENTS=!FAILED_AGENTS! %%A
    )

    :: Clear CUDA cache between runs
    python -c "import torch; torch.cuda.empty_cache()" >nul 2>&1
)

:: ── Summary ──────────────────────────────────────────────────────────────────
echo.
echo  ================================================================
echo   TRAINING COMPLETE
echo   Passed : %PASS_COUNT%
echo   Failed : %FAIL_COUNT%
if not "%FAILED_AGENTS%"=="" echo   Failed agents:%FAILED_AGENTS%
echo.
echo   Next steps:
echo     1. Run Modelfile rebuild for each agent:
echo        ollama create codex-sovereign -f native\windows\Modelfiles\Modelfile.codex
echo     2. Restart Ollama to load updated models
echo     3. Run SAGE cycles — each model now trained on its own elite proposals
echo        python run_sage_cycles.py 14
echo  ================================================================
echo.
pause
