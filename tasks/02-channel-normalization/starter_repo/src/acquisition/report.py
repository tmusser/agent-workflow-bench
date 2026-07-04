from __future__ import annotations

from pathlib import Path

import pandas as pd

from .load import fixture_dir, load_leads
from .metrics import summarize_channels


def weekly_channel_report(fixtures_dir: str | Path | None = None) -> pd.DataFrame:
    base = Path(fixtures_dir) if fixtures_dir is not None else fixture_dir()
    leads = load_leads(base / "leads.csv")
    return summarize_channels(leads)


def email_channel_row(fixtures_dir: str | Path | None = None) -> dict[str, object]:
    report = weekly_channel_report(fixtures_dir)
    row = report[report["channel"] == "email"]
    if row.empty:
        raise LookupError("No email channel row found")
    return row.iloc[0].to_dict()
