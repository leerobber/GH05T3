@echo off
echo.
echo  [TUNNEL] Starting named tunnel: sovereignnation-demo
echo  Requires SETUP_TUNNEL.bat to have been run first.
echo.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel run sovereignnation-demo
