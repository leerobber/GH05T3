@echo off
REM ============================================================
REM  rebuild_avery.bat
REM  Run AFTER Kaggle training finishes and LoRA is on HuggingFace.
REM  Merges Avery LoRA with Qwen2.5-3B-Instruct, converts to GGUF,
REM  loads into Ollama, and runs a smoke test.
REM ============================================================

echo.
echo ============================================================
echo   Avery 3B Rebuild Pipeline
echo   Run this after Kaggle training completes
echo ============================================================
echo.

set PYTHON=C:\Users\leer4\AppData\Local\Programs\Python\Python312\python.exe
set SCRIPT=C:\Users\leer4\GH05T3\merge_avery_3b.py

REM Verify Kaggle LoRA exists on HuggingFace before starting
echo [CHECK] Verifying LoRA is available on HuggingFace...
%PYTHON% -c "from huggingface_hub import HfApi; api=HfApi(); files=api.list_repo_files('tastytator/avery-sovereign-lora', token=open('C:/Users/leer4/.cache/huggingface/token').read().strip()); files=list(files); print(f'  LoRA files found: {len(files)}'); [print(f'    - {f}') for f in files[:10]]" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Could not access tastytator/avery-sovereign-lora on HuggingFace.
    echo         Has the Kaggle training finished? Check your Kaggle notebook.
    echo.
    pause
    exit /b 1
)

echo.
echo [START] Running merge pipeline...
echo         This will take 20-40 minutes (CPU merge + GGUF conversion)
echo         Log: C:\Users\leer4\GH05T3\merge_avery_3b.log
echo.

%PYTHON% %SCRIPT%

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FAILED] Pipeline failed. Check log:
    echo          C:\Users\leer4\GH05T3\merge_avery_3b.log
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   SUCCESS - Avery 3B is live in Ollama
echo   Test it: ollama run avery-sovereign
echo ============================================================
echo.
pause
