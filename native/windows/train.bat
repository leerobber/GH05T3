@echo off
:: GH05T3 Local Training Launcher
:: Trains Qwen2.5-Coder-3B + LoRA on RTX 5050 (Blackwell, CUDA 12.8)
:: Adapter saves to: backend\models\gh05t3_lora_adapter\
::
:: Usage: double-click, or from repo root: native\windows\train.bat
:: First run installs deps (~5 min). Subsequent runs go straight to training.

setlocal enabledelayedexpansion
cd /d "%~dp0..\.."
set APP=%CD%

echo.
echo  =============================================
echo   GH05T3 LOCAL TRAINING
echo   Model  : Qwen2.5-Coder-3B + LoRA rank 16
echo   GPU    : RTX 5050 (Blackwell, CUDA 12.8)
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
:: Check for PyTorch with CUDA. If not found, install the whole stack.
python -c "import torch; assert torch.cuda.is_available()" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing PyTorch 2.6 + CUDA 12.8 for RTX 5050 Blackwell...
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 -q
    if errorlevel 1 ( echo [ERROR] PyTorch install failed & pause & exit /b 1 )
    echo [SETUP] Installing training dependencies...
    pip install ^
        "transformers==4.40.2" ^
        "peft==0.10.0" ^
        "trl==0.8.6" ^
        "accelerate==0.29.3" ^
        "datasets==2.19.0" ^
        "huggingface_hub>=0.22.0" ^
        "kaggle" -q
    if errorlevel 1 ( echo [ERROR] Dep install failed & pause & exit /b 1 )
    echo [SETUP] Done.
    echo.
)

:: ── Run training ──────────────────────────────────────────────────────────────
echo [TRAIN] Starting...
echo.
python backend\training\train_local.py
set EXIT=%ERRORLEVEL%

echo.
if %EXIT% equ 0 (
    echo  =============================================
    echo   TRAINING COMPLETE
    echo   Adapter : backend\models\gh05t3_lora_adapter
    echo   Next    : add LLM_PROVIDER=gh05t3 to backend\.env
    echo            then run run.bat to start the stack
    echo  =============================================
) else (
    echo  [ERROR] Training failed ^(exit code %EXIT%^) — check output above
)
echo.
pause
