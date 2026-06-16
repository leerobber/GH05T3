"""GH05T3 backend launcher — sets correct sys.path then fires uvicorn."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
for p in (str(ROOT), str(ROOT / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

import uvicorn  # noqa: E402

uvicorn.run("backend.server:app", host="0.0.0.0", port=8001, log_level="info")
