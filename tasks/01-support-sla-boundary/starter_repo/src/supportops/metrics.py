from __future__ import annotations

import pandas as pd

SLA_HOURS = {
    "urgent": 4,
    "standard": 24,
}


def add_sla_fields(tickets: pd.DataFrame) -> pd.DataFrame:
    """Add response-time and SLA breach fields to ticket rows."""
    result = tickets.copy()
    response_delta = result["first_response_at"] - result["created_at"]
    result["response_hours"] = response_delta.dt.total_seconds() / 3600
    result["sla_hours"] = result["priority"].map(SLA_HOURS)

    # BUG: exact-boundary responses are allowed, but this treats them as breaches.
    result["sla_breached"] = result["response_hours"] >= result["sla_hours"]
    return result


def summarize_sla(tickets: pd.DataFrame) -> pd.DataFrame:
    enriched = add_sla_fields(tickets)
    grouped = (
        enriched.groupby("priority", sort=True)
        .agg(total_tickets=("ticket_id", "nunique"), breached_tickets=("sla_breached", "sum"))
        .reset_index()
    )
    grouped["breach_rate"] = grouped["breached_tickets"] / grouped["total_tickets"]
    grouped["breached_tickets"] = grouped["breached_tickets"].astype(int)
    return grouped[["priority", "total_tickets", "breached_tickets", "breach_rate"]]
