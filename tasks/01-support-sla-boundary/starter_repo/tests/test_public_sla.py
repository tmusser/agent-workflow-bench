from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supportops.metrics import add_sla_fields, summarize_sla  # noqa: E402


def test_standard_ticket_at_exact_24_hour_boundary_is_not_breached():
    tickets = pd.DataFrame(
        [
            {
                "ticket_id": "PUBLIC-1",
                "priority": "standard",
                "created_at": pd.Timestamp("2026-01-01 09:00:00"),
                "first_response_at": pd.Timestamp("2026-01-02 09:00:00"),
            }
        ]
    )

    enriched = add_sla_fields(tickets)

    assert bool(enriched.iloc[0]["sla_breached"]) is False


def test_report_keeps_existing_columns_and_priority_order():
    tickets = pd.DataFrame(
        [
            {
                "ticket_id": "PUBLIC-2",
                "priority": "urgent",
                "created_at": pd.Timestamp("2026-01-01 09:00:00"),
                "first_response_at": pd.Timestamp("2026-01-01 13:30:00"),
            },
            {
                "ticket_id": "PUBLIC-3",
                "priority": "standard",
                "created_at": pd.Timestamp("2026-01-01 09:00:00"),
                "first_response_at": pd.Timestamp("2026-01-01 10:00:00"),
            },
        ]
    )

    report = summarize_sla(tickets)

    assert list(report.columns) == ["priority", "total_tickets", "breached_tickets", "breach_rate"]
    assert report["priority"].tolist() == ["standard", "urgent"]
    urgent = report[report["priority"] == "urgent"].iloc[0]
    assert int(urgent["breached_tickets"]) == 1
