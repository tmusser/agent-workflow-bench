from __future__ import annotations

from pathlib import Path

from churncalc.load import load_cancellation_events, load_plan_history
from churncalc.metrics import calculate_monthly_churn

ROOT = Path(__file__).resolve().parents[1]


def test_march_enterprise_churn_is_not_above_100_percent():
    plan_history = load_plan_history(ROOT / "fixtures" / "plan_history.csv")
    cancellations = load_cancellation_events(ROOT / "fixtures" / "cancellation_events.csv")

    churn = calculate_monthly_churn(plan_history, cancellations)

    march_enterprise = churn[(churn["month"] == "2024-03") & (churn["plan"] == "enterprise")]
    assert not march_enterprise.empty
    assert float(march_enterprise.iloc[0]["churn_rate"]) <= 1.0
