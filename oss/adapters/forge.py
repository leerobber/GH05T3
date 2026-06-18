"""Bridge Omni Forge to backend training pipeline."""
from __future__ import annotations

import logging

LOG = logging.getLogger("oss.adapter.forge")


def trigger_forge_cycle(**kwargs) -> dict:
    from oss.forge.agency import get_agency
    record = get_agency().run_cycle(**kwargs)
    return record.to_dict()


def forge_status() -> dict:
    from oss.forge.agency import get_agency
    return get_agency().status()