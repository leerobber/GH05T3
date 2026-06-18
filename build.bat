@echo off
setlocal enableextensions
set APP=%~dp0
cd /d "%APP%frontend"

where yarn >nul 2>&1
if errorlevel 1 (
    echo ERROR: yarn not found. Install Node.js and enable yarn.
    exit /b 1
)

if not exist node_modules (
    echo Installing frontend dependencies...
    call yarn install --frozen-lockfile
    if errorlevel 1 exit /b 1
)

echo Building frontend...
call yarn build
exit /b %ERRORLEVEL%