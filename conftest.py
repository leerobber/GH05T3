"""
Repo-root conftest — loaded by pytest before any test directory conftest.
Sets env vars and sys.path here so they're in place for EVERY import
that happens during collection (including module-level imports in test files).
"""
import os
import sys
from pathlib import Path

# ── UTF-8 mode — prevents charmap codec errors on Windows with box-drawing chars ─
os.environ.setdefault("PYTHONUTF8", "1")

# ── License gate + test mode — must be set before gateway_v3 is imported ─────
os.environ.setdefault("AETHYRO_SKIP_LICENSE", "1")
os.environ.setdefault("GH05T3_TEST_MODE", "1")

# ── sys.path — backend/ must be resolvable for bare imports (swarm, evolution…) ─
_ROOT    = Path(__file__).resolve().parent
_BACKEND = _ROOT / "backend"
# backend/ at position 0 so backend packages (memory, swarm, evolution…) are
# found before the root-level counterparts that lack some submodules.
# '' (CWD resolves to repo root) is already in sys.path; we ensure backend
# is explicitly before it by removing duplicates first and re-inserting.
for _p in (str(_BACKEND), str(_ROOT)):
    while _p in sys.path:
        sys.path.remove(_p)
sys.path.insert(0, str(_ROOT))      # position 1 after next insert
sys.path.insert(0, str(_BACKEND))   # position 0 — backend owns memory, swarm, etc.

# ── Pre-load root oss package so backend/oss never shadows it ────────────────
# root/oss has kernel, dna, schemas, etc.; backend/oss is unrelated.
# Injecting it here ensures all "from oss.xxx import ..." resolve to root/oss
# even though backend/ comes first in sys.path.
import importlib.util as _ilu

_oss_init = _ROOT / "oss" / "__init__.py"
if _oss_init.exists() and "oss" not in sys.modules:
    _oss_spec = _ilu.spec_from_file_location(
        "oss", str(_oss_init),
        submodule_search_locations=[str(_ROOT / "oss")],
    )
    if _oss_spec and _oss_spec.loader:
        _oss_mod = _ilu.module_from_spec(_oss_spec)
        sys.modules["oss"] = _oss_mod
        _oss_spec.loader.exec_module(_oss_mod)
