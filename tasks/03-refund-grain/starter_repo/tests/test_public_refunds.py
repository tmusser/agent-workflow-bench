from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from commerce.metrics import calculate_product_refund_rates  # noqa: E402


def test_duplicate_refund_events_count_one_refunded_order():
    orders = pd.DataFrame(
        [
            {"order_id": "PUBLIC-1", "product": "widget", "order_total": 100},
            {"order_id": "PUBLIC-2", "product": "widget", "order_total": 50},
        ]
    )
    refunds = pd.DataFrame(
        [
            {
                "refund_id": "PUBLIC-R1",
                "order_id": "PUBLIC-1",
                "refunded_at": pd.Timestamp("2026-03-01"),
                "amount": 25,
            },
            {
                "refund_id": "PUBLIC-R2",
                "order_id": "PUBLIC-1",
                "refunded_at": pd.Timestamp("2026-03-02"),
                "amount": 75,
            },
        ]
    )

    report = calculate_product_refund_rates(orders, refunds)

    row = report.iloc[0]
    assert int(row["total_orders"]) == 2
    assert int(row["refunded_orders"]) == 1
    assert float(row["refund_rate"]) == 0.5


def test_report_keeps_existing_columns_and_sorted_product_order():
    orders = pd.DataFrame(
        [
            {"order_id": "PUBLIC-3", "product": "widget", "order_total": 100},
            {"order_id": "PUBLIC-4", "product": "gadget", "order_total": 100},
        ]
    )
    refunds = pd.DataFrame(
        [
            {
                "refund_id": "PUBLIC-R3",
                "order_id": "PUBLIC-4",
                "refunded_at": pd.Timestamp("2026-03-01"),
                "amount": 100,
            }
        ]
    )

    report = calculate_product_refund_rates(orders, refunds)

    assert list(report.columns) == ["product", "total_orders", "refunded_orders", "refund_rate"]
    assert report["product"].tolist() == ["gadget", "widget"]
    widget = report[report["product"] == "widget"].iloc[0]
    assert int(widget["refunded_orders"]) == 0
    assert float(widget["refund_rate"]) == 0.0
