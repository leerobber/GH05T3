@echo off
REM ─── GH05T3 Sovereign Companion v2 launcher ──────────────────────────────
REM Edit the two env vars below, then double-click this file.
REM GHOST_GATEWAY_URL = your GH05T3 backend (dashboard URL)
REM PAIR_CODE         = 6-digit code from the Companion panel

set GHOST_GATEWAY_URL=https://tatorot-dashboard.preview.emergentagent.com
set PAIR_CODE=

if "%PAIR_CODE%"=="" (
  echo.
  echo   Paste the 6-digit pair code from the dashboard Companion panel:
  set /p PAIR_CODE="  > "
)

python ghost_agent_v2.py ^
  --gateway "%GHOST_GATEWAY_URL%" ^
  --pair-code "%PAIR_CODE%" ^
  --label "%COMPUTERNAME%" ^
  --screen-read --ghosteye --ghosteye-ocr --ghosteye-interval 15 ^
  --shell-exec --clipboard --notify ^
  --fs-read "%USERPROFILE%\code" ^
  --fs-write "%USERPROFILE%\code" ^
  --react --llm-port 8000 ^
  --health-interval 60

pause
