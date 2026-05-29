@echo off
title Phi-3.5-mini Service :8112
cd /d "%~dp0"
set "PHIPY=C:\Users\leer4\phi_dml_env\Scripts\python.exe"

echo Starting Phi-3.5-mini service on port 8112 (foreground / visible)...
echo Model loads in ~5-7s on the RTX 5050 (CUDA EP). Watch for "Phi-3.5-mini ready".
echo.
"%PHIPY%" phi_service.py
pause
