@echo off
REM Run the full GH05T3 pytest suite using the backend venv (Windows canonical).
cd /d "%~dp0..\.."
set PY=%CD%\backend\.venv\Scripts\python.exe
if not exist "%PY%" (
  echo [test.bat] backend venv missing. Run native\windows\install.ps1 first.
  exit /b 1
)
set AETHYRO_SKIP_LICENSE=1
set GH05T3_TEST_MODE=1
"%PY%" -m pytest tests backend/tests -q %*