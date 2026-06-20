@echo off
title GH05T3 — Kill Managed Ports
color 0C
echo.
echo  Killing all GH05T3 managed ports...
echo.

for %%P in (8001 8002 8081 8090 8098 8099 8111 7861 7862 3210 8765) do (
    for /f "tokens=5" %%A in ('netstat -ano 2^>nul ^| findstr "0.0.0.0:%%P "') do (
        if not "%%A"=="0" (
            echo  Killing PID %%A on port %%P
            taskkill /F /PID %%A >nul 2>&1
        )
    )
)

echo.
echo  Done. All GH05T3 ports cleared.
echo  You can now run START_ALL.bat
echo.
pause
