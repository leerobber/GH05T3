@echo off
SET AETHYRO_SKIP_LICENSE=1
SET PYTHONIOENCODING=utf-8
cd /d "C:\Users\leer4\GH05T3\backend"
"C:\Users\leer4\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn gateway_v3:app --host 0.0.0.0 --port 8002
