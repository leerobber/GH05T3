#!/usr/bin/env python3
"""Streamlit dashboard for OSS SaaS product-design lab metrics."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.lab.metrics import load_logs, run_streamlit_dashboard, trade_logs_from_transactions
from oss.substrate.value_flow import get_value_flow


def main() -> None:
    logs = load_logs()
    trades = trade_logs_from_transactions(get_value_flow().transaction_history)
    run_streamlit_dashboard(logs, trades)


if __name__ == "__main__":
    main()