from __future__ import annotations

from pathlib import Path

import pandas as pd

from .load import fixture_dir, load_tickets
from .metrics import summarize_sla


def weekly_sla_report(fixtures_dir: str | Path | None = None) -> pd.DataFrame:
    base = Path(fixtures_dir) if fixtures_dir is not None else fixture_dir()
    tickets = load_tickets(base / "tickets.csv")
    return summarize_sla(tickets)


def standard_sla_row(fixtures_dir: str | Path | None = None) -> dict[str, object]:
    report = weekly_sla_report(fixtures_dir)
    row = report[report["priority"] == "standard"]
    if row.empty:
        raise LookupError("No standard SLA row found")
    return row.iloc[0].to_dict()
