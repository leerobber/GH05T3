@echo off
cd /d "C:\Users\leer4\GH05T3\sovereignnation"
call "C:\Users\leer4\GH05T3\.venv\Scripts\activate.bat"
python ghost_chat.py --model qwen3:8b %*
