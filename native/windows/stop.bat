@echo off
cd /d "%~dp0"
set PY=%~dp0..\..\backend\.venv\Scripts\python.exe
if not exist "%PY%" set PY=python
"%PY%" "%~dp0..\..\scripts\runtime\supervisor.py" --stop
