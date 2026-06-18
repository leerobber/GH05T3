@echo off
:: Sovereign Train Kernel — agent-native fine-tuning (no TRL)
cd /d "%~dp0..\.."
echo.
echo  SOVEREIGN TRAIN — agent-native, constitution-enforced
echo  Usage: sovereign_train.bat [AGENT] [STEPS]
echo  Example: sovereign_train.bat GH05T3 80
echo.
set AGENT=%~1
if "%AGENT%"=="" set AGENT=GH05T3
set STEPS=%~2
if "%STEPS%"=="" set STEPS=80
backend\.venv\Scripts\python.exe oss\cli\train_run.py --agent %AGENT% --steps %STEPS% --forge-only --model Qwen/Qwen2.5-Coder-3B-Instruct
pause