@echo off
echo ================================================
echo   AVERY 3B FULL TRAINING PIPELINE
echo ================================================
echo.

cd /d "C:\Users\leer4\GH05T3"

:: Load environment variables from .env
for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
    if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
)

echo HF_TOKEN   : %HF_TOKEN:~0,8%...
echo RUNPOD_KEY : %RUNPOD_API_KEY:~0,8%...
echo.

:: Run the full pipeline
python avery_pipeline.py %*

echo.
if %ERRORLEVEL%==0 (
    echo Pipeline complete! Test Avery:
    echo   ollama run avery-sovereign
) else (
    echo Pipeline FAILED. Check output above.
)
pause
