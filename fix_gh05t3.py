import os
import sys
import subprocess

PROJECT_ROOT = os.getcwd()
print(f"[+] Fixing project at: {PROJECT_ROOT}")

# -------------------------
# 1. Scan Python files
# -------------------------
py_files = []
for root, dirs, files in os.walk(PROJECT_ROOT):
    for file in files:
        if file.endswith(".py") and file != "fix_gh05t3.py":
            py_files.append(os.path.join(root, file))

print(f"[+] Found {len(py_files)} Python files")

# -------------------------
# 2. Create main.py
# -------------------------
main_path = os.path.join(PROJECT_ROOT, "main.py")

MAIN_TEMPLATE = '''import sys
import os

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def run():
    print("GH05T3 starting...")

    try:
        import core
        print("Loaded core")
    except Exception as e:
        print("No core module:", e)

    try:
        import app
        print("Loaded app")
    except Exception as e:
        print("No app module:", e)

    print("System ready.")
    input("Press Enter to exit...")

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"Fatal error: {e}")
        input("Press Enter to exit...")
'''

with open(main_path, "w", encoding="utf-8") as f:
    f.write(MAIN_TEMPLATE)

print("[+] Created main.py")

# -------------------------
# 3. Ensure PyInstaller
# -------------------------
print("[+] Installing PyInstaller...")
subprocess.call([sys.executable, "-m", "pip", "install", "pyinstaller"])

# -------------------------
# 4. Build EXE
# -------------------------
print("[+] Building EXE...")

subprocess.call([
    "pyinstaller",
    "--onefile",
    "--noconsole",
    "main.py"
])

print("[?] DONE - Check /dist/main.exe")
