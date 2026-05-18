@echo off
title GH05T3 Supervisor
cd /d "%~dp0"
set PY=%~dp0backend\.venv\Scripts\python.exe
if not exist "%PY%" set PY=python
start "GH05T3 Supervisor" /min "%PY%" "%~dp0supervisor.py"
echo GH05T3 starting... check logs\supervisor.log or http://localhost:8090/status
