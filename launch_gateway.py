"""GH05T3 gateway_v3 launcher — sets correct sys.path then fires uvicorn."""
import sys
import os

ROOT = r"C:\Users\leer4\GH05T3"
os.chdir(ROOT)
for p in [ROOT, os.path.join(ROOT, "backend")]:
    if p not in sys.path:
        sys.path.insert(0, p)

import uvicorn
uvicorn.run("backend.gateway_v3:app", host="0.0.0.0", port=8003, log_level="info")
