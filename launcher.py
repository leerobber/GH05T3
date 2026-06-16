#!/usr/bin/env python3
"""Clean GH05T3 launcher - minimal, no flashing."""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

IS_WINDOWS = sys.platform == "win32"
NEW_CONSOLE = subprocess.CREATE_NEW_CONSOLE if IS_WINDOWS else 0

print("=" * 50)
print("GH05T3 CLEAN STARTUP")
print("=" * 50)

# Kill any existing processes (Windows only — best effort)
print("\n[1/5] Cleaning old processes...")
if IS_WINDOWS:
    os.system('taskkill /F /IM python.exe /FI "WINDOWTITLE eq mongo*" 2>nul')
    os.system('taskkill /F /IM python.exe /FI "WINDOWTITLE eq gateway*" 2>nul')
    os.system('taskkill /F /IM python.exe /FI "WINDOWTITLE eq backend*" 2>nul')
time.sleep(1)

# MongoDB
print("[2/5] Starting MongoDB...")
os.makedirs("mongo-data", exist_ok=True)
subprocess.Popen(
    ["mongod", "--dbpath", "mongo-data", "--port", "27017", "--bind_ip", "127.0.0.1"],
    creationflags=NEW_CONSOLE,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
time.sleep(2)

# Backend server
print("[3/5] Starting backend:8001...")
subprocess.Popen(
    ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"],
    cwd="backend",
    creationflags=NEW_CONSOLE,
)
time.sleep(2)

# Gateway
print("[4/5] Starting gateway:8002...")
subprocess.Popen(
    ["python", "-m", "uvicorn", "gateway_v3:app", "--host", "0.0.0.0", "--port", "8002"],
    cwd="backend",
    creationflags=NEW_CONSOLE,
)
time.sleep(2)

# Frontend
print("[5/5] Starting frontend:3210...")
subprocess.Popen(
    ["python", "-m", "http.server", "3210", "--directory", str(ROOT / "frontend" / "build")],
    creationflags=NEW_CONSOLE,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
time.sleep(2)

print("\n" + "=" * 50)
print("All services started")
print("=" * 50)
print("\nDashboard: http://localhost:3210")
print("Gateway:   http://localhost:8002")

if IS_WINDOWS:
    print("\nOpening browser...")
    os.system("start http://localhost:3210")

print("\nPress Ctrl+C to stop all services")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\nShutting down...")
