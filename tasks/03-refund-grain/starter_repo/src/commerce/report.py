from __future__ import annotations

from pathlib import Path

import pandas as pd

from .load import fixture_dir, load_orders, load_refund_events
from .metrics import calculate_product_refund_rates


def weekly_refund_report(fixtures_dir: str | Path | None = None) -> pd.DataFrame:
    base = Path(fixtures_dir) if fixtures_dir is not None else fixture_dir()
    orders = load_orders(base / "orders.csv")
    refunds = load_refund_events(base / "refund_events.csv")
    return calculate_product_refund_rates(orders, refunds)


def widget_refund_row(fixtures_dir: str | Path | None = None) -> dict[str, object]:
    report = weekly_refund_report(fixtures_dir)
    row = report[report["product"] == "widget"]
    if row.empty:
        raise LookupError("No widget refund row found")
    return row.iloc[0].to_dict()
