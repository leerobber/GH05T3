@echo off
echo.
echo  [DEMO MODE] Activating...
echo.
REM 1) Create demo flag
echo. > "C:\Users\leer4\GH05T3\data\demo_mode.flag"
echo  [1/3] Demo flag created.
REM 2) Kill stray Ollama-competing processes
echo  [2/3] Clearing stray processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0demo_on_helper.ps1"
echo.
echo  ==================================================
echo   DEMO MODE ACTIVE
echo   - Training loops paused (flag set)
echo   - Stray processes cleared
echo   - gh05t3:latest stays in VRAM via KAIROS cycles
echo   - Run DEMO_OFF.bat to resume training when done
echo  ==================================================
echo.