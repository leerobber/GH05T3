"""GH05T3 gateway_v3 launcher — sets correct sys.path then fires uvicorn."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
for p in (str(ROOT), str(ROOT / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

import uvicorn  # noqa: E402

# Gateway v3 standard port is 8002 (see CLAUDE.md port map and .env.example).
port = int(os.environ.get("GATEWAY_PORT", "8002"))
uvicorn.run("backend.gateway_v3:app", host="0.0.0.0", port=port, log_level="info")
