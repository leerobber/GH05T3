@echo off
:: GH05T3 Intelligence Training — systems, code, data (500 steps, mega-dataset)
cd /d "%~dp0..\.."
echo.
echo  INTELLIGENCE TRAIN — systems / code / data reasoning
echo  Dataset: forge + elite + reasoning + recall + anchors
echo  Steps: 500  Model: Qwen2.5-Coder-3B  Output: gh05t3_lora_adapter
echo.
echo  Stop inference on :8010 first to free GPU VRAM.
echo.
backend\.venv\Scripts\python.exe oss\cli\forge_run.py --min-tier silver --no-pipeline
backend\.venv\Scripts\python.exe oss\cli\intelligence_train.py --steps 500 --model Qwen/Qwen2.5-Coder-3B-Instruct --output backend\models\gh05t3_lora_adapter --recall-cap 2000
pause