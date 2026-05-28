@echo off
echo.
echo  [QUICKTUNNEL] Starting temporary cloudflare tunnel on port 7861
echo  No login required. URL changes on every restart.
echo  Copy the printed URL and paste it into landing/index.html as DEMO_URL.
echo.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:7861
