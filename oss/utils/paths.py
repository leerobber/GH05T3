"""
Central import helper for the OSS layer.

Ensures that whether the process starts from repo root, backend/, or elsewhere,
imports for both `oss.*` and `backend.*` resolve cleanly.

Use this instead of sprinkling sys.path.insert throughout the codebase.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple


_OSS_ROOT: Path | None = None
_BACKEND: Path | None = None


def get_oss_root() -> Path:
    global _OSS_ROOT
    if _OSS_ROOT is None:
        # router.py lives at oss/api/router.py → parents[2] == repo root
        _OSS_ROOT = Path(__file__).resolve().parents[2]
    return _OSS_ROOT


def get_backend_dir() -> Path:
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = get_oss_root() / "backend"
    return _BACKEND


def ensure_oss_paths() -> Tuple[str, str]:
    """
    Idempotent. Call once at the top of modules that need cross-layer imports
    (e.g. when FastAPI mounts oss.api.router from gateway_v3.py).

    Returns (root_str, backend_str)
    """
    root = str(get_oss_root())
    backend = str(get_backend_dir())

    if root not in sys.path:
        sys.path.insert(0, root)
    if backend not in sys.path:
        sys.path.insert(0, backend)

    return root, backend


# Backwards-compatible alias used in router before centralization
_ensure_oss_paths = ensure_oss_paths
