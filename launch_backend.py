"""GH05T3 backend launcher — sets correct sys.path then fires uvicorn."""
import sys
import os

ROOT = r"C:\Users\leer4\GH05T3"
os.chdir(ROOT)
for p in [ROOT, os.path.join(ROOT, "backend")]:
    if p not in sys.path:
        sys.path.insert(0, p)

import uvicorn
uvicorn.run("backend.server:app", host="0.0.0.0", port=8001, log_level="info")
