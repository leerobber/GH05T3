@echo off
echo.
echo  ================================================
echo   SovereignNation — Cloudflare Tunnel Setup
echo   Run this ONCE to create your permanent tunnel.
echo  ================================================
echo.
echo  STEP 1: Authenticate with Cloudflare
echo  (Opens browser — log in with your Cloudflare account)
echo  If you don't have one, create a free account at cloudflare.com first.
echo.
pause
"C:\Program Files (x86)\cloudflared\cloudflared.exe" login
echo.
echo  STEP 2: Create the named tunnel
echo.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel create sovereignnation-demo
echo.
echo  ================================================
echo   TUNNEL CREATED.
echo.
echo   Next steps:
echo.
echo   Option A — You own a domain (e.g. sovereignnation.ai):
echo     1. Add domain to Cloudflare (free) at cloudflare.com
echo     2. Run:
echo        cloudflared tunnel route dns sovereignnation-demo demo.yourdomain.com
echo     3. Run START_TUNNEL.bat to start (permanent URL: demo.yourdomain.com)
echo.
echo   Option B — No domain yet (free subdomain option):
echo     Buy a cheap domain on Namecheap (~$10/yr) and point it to Cloudflare.
echo     OR use START_QUICKTUNNEL.bat for a temporary URL (changes on restart).
echo.
echo   The tunnel credentials file is saved at:
echo     C:\Users\leer4\.cloudflared\
echo  ================================================
echo.
pause
