@echo off
:: GH05T3 Local Training Launcher
:: Trains Qwen2.5-7B-Instruct + QLoRA (4-bit) on RTX 5050 (Blackwell, CUDA 12.8)
:: First run: ~5 min dep install + model download.  Training: ~30-45 min.
:: Output: backend\models\gh05t3_lora_adapter\
::
:: Run from anywhere — script resolves the repo root automatically.

setlocal enabledelayedexpansion
cd /d "%~dp0..\.."
set APP=%CD%

echo.
echo  =============================================
echo   GH05T3 LOCAL TRAINING
echo   Model  : Qwen2.5-7B-Instruct + QLoRA 4-bit
echo   GPU    : RTX 5050  ^(Blackwell, CUDA 12.8^)
echo   Output : backend\models\gh05t3_lora_adapter
echo  =============================================
echo.

:: ── Python check ──────────────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Run native\windows\install.ps1 first.
    pause & exit /b 1
)

:: ── One-time dep install ──────────────────────────────────────────────────────
:: Detect if PyTorch with CUDA is present.  If not, install the full stack.
python -c "import torch, bitsandbytes; assert torch.cuda.is_available()" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing training stack for Blackwell RTX 5050...
    echo         PyTorch 2.6 + CUDA 12.8, bitsandbytes, transformers, peft, trl
    echo.

    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 -q
    if errorlevel 1 ( echo [ERROR] PyTorch install failed & pause & exit /b 1 )

    pip install ^
        "transformers==4.40.2" ^
        "peft==0.10.0" ^
        "trl==0.8.6" ^
        "accelerate==0.29.3" ^
        "datasets==2.19.0" ^
        "huggingface_hub>=0.22.0" ^
        "bitsandbytes>=0.44.0" ^
        "kaggle" -q
    if errorlevel 1 ( echo [ERROR] Dep install failed & pause & exit /b 1 )

    echo [SETUP] Done.
    echo.
)

:: ── Run training ──────────────────────────────────────────────────────────────
echo [TRAIN] Starting Qwen2.5-7B QLoRA...
echo         Watch loss at steps 10, 20, 30 — should be 1.5-3.5 and decreasing.
echo         If loss is 0.0 or 265+ at step 10: gradient collapse — check output.
echo.
python backend\training\train_local.py
set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE% equ 0 (
    echo  =============================================
    echo   TRAINING COMPLETE
    echo   Adapter : backend\models\gh05t3_lora_adapter
    echo.
    echo   Next steps:
    echo     1. Open backend\.env
    echo     2. Add:  LLM_PROVIDER=gh05t3
    echo     3. Run:  run.bat
    echo     Avery will use the fine-tuned model on port 8010.
    echo  =============================================
) else (
    echo  [ERROR] Training failed ^(exit %EXIT_CODE%^) — see output above
    echo  Common causes:
    echo    - bitsandbytes not installed: pip install "bitsandbytes>=0.44.0"
    echo    - Wrong PyTorch: pip install torch --index-url .../whl/cu128
    echo    - OOM: edit train_local.py, set BATCH = 1
)
echo.
pause
