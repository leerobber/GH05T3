@echo off
:: GH05T3 Domain Adapter Training
:: Trains 4 specialist LoRA adapters sequentially on RTX 5050:
::   security_adapter  — SENTINEL: CVE analysis, threat detection
::   code_adapter      — FORGE:    code review, architecture
::   research_adapter  — ORACLE:   survey, synthesis, literature
::   ops_adapter       — NEXUS:    deployment, incident response, capacity
::
:: Each adapter: ~30-45 min.  Total: ~2-3 hrs.
:: Run train.bat first to ensure the default adapter exists.
::
:: Run from anywhere — script resolves repo root automatically.

setlocal enabledelayedexpansion
cd /d "%~dp0..\.."
set APP=%CD%

echo.
echo  =============================================
echo   GH05T3 DOMAIN ADAPTER TRAINING
echo   Trains: security / code / research / ops
echo   GPU    : RTX 5050  ^(Blackwell, CUDA 12.8^)
echo   Each   : ~30-45 min   Total: ~2-3 hrs
echo  =============================================
echo.

:: ── Python + deps check ────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Run native\windows\install.ps1 first.
    pause & exit /b 1
)
python -c "import torch, bitsandbytes; assert torch.cuda.is_available()" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyTorch+CUDA not found. Run train.bat first to install deps.
    pause & exit /b 1
)

:: ── Train each domain ──────────────────────────────────────────────────────
set DOMAINS=security code research ops
set FAILED=

for %%D in (%DOMAINS%) do (
    echo.
    echo  ─────────────────────────────────────────────
    echo  [DOMAIN] Training %%D adapter...
    echo  Output : backend\models\%%D_adapter
    echo  ─────────────────────────────────────────────
    echo.

    python backend\training\train_local.py --domain %%D
    set EXIT=!ERRORLEVEL!

    if !EXIT! equ 0 (
        echo  [OK] %%D adapter complete → backend\models\%%D_adapter
    ) else (
        echo  [ERROR] %%D adapter FAILED ^(exit !EXIT!^)
        set FAILED=!FAILED! %%D
    )
    echo.
)

:: ── Summary ────────────────────────────────────────────────────────────────
echo.
echo  =============================================
if "%FAILED%"=="" (
    echo   ALL DOMAIN ADAPTERS TRAINED SUCCESSFULLY
    echo.
    echo   Adapters ready:
    echo     backend\models\security_adapter\
    echo     backend\models\code_adapter\
    echo     backend\models\research_adapter\
    echo     backend\models\ops_adapter\
    echo.
    echo   LoRAFarm will auto-route tasks to the right adapter.
    echo   No config change needed — restart run.bat.
) else (
    echo   FAILED DOMAINS:%FAILED%
    echo.
    echo   Check output above for error details.
    echo   Common fix: set BATCH=1 in train_local.py if OOM
)
echo  =============================================
echo.
pause
