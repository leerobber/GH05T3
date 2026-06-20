@echo off
title GH05T3 — WSL Launcher
color 0A
echo.
echo  ============================================================
echo   GH05T3 — LAUNCHING IN WSL
echo  ============================================================
echo.
echo  Starting WSL services (gateway + backend)...
echo  Logs: \\wsl$\Ubuntu\tmp\gh05t3-wsl\
echo.
wsl -e bash -c "bash /mnt/c/Users/leer4/GH05T3/scripts/wsl_start.sh"
echo.
pause
