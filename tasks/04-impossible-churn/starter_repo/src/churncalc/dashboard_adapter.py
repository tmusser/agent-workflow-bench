from __future__ import annotations

from pathlib import Path

import pandas as pd

from .load import fixture_dir, load_cancellation_events, load_plan_history
from .metrics import calculate_monthly_churn


def get_dashboard_churn(fixtures_dir: str | Path | None = None) -> pd.DataFrame:
    base = Path(fixtures_dir) if fixtures_dir is not None else fixture_dir()
    plan_history = load_plan_history(base / "plan_history.csv")
    cancellations = load_cancellation_events(base / "cancellation_events.csv")
    return calculate_monthly_churn(plan_history, cancellations)


def get_march_enterprise_churn(fixtures_dir: str | Path | None = None) -> dict[str, object]:
    churn = get_dashboard_churn(fixtures_dir)
    row = churn[(churn["month"] == "2024-03") & (churn["plan"] == "enterprise")]
    if row.empty:
        raise LookupError("No March enterprise churn row found")
    return row.iloc[0].to_dict()
