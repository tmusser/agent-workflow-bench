from __future__ import annotations

from pathlib import Path

from churncalc.load import load_cancellation_events, load_plan_history
from churncalc.metrics import active_customer_denominators, calculate_monthly_churn

ROOT = Path(__file__).resolve().parents[1]


def test_active_customer_denominator_counts_unique_customers_at_month_start():
    plan_history = load_plan_history(ROOT / "fixtures" / "plan_history.csv")
    denominators = active_customer_denominators(plan_history, ["2024-02"])

    pro = denominators[(denominators["month"] == "2024-02") & (denominators["plan"] == "pro")].iloc[0]
    enterprise = denominators[(denominators["month"] == "2024-02") & (denominators["plan"] == "enterprise")].iloc[0]

    assert int(pro["starting_customers"]) == 5
    assert int(enterprise["starting_customers"]) == 6


def test_existing_pro_churn_behavior_is_preserved():
    plan_history = load_plan_history(ROOT / "fixtures" / "plan_history.csv")
    cancellations = load_cancellation_events(ROOT / "fixtures" / "cancellation_events.csv")

    churn = calculate_monthly_churn(plan_history, cancellations)
    row = churn[(churn["month"] == "2024-02") & (churn["plan"] == "pro")].iloc[0]

    assert int(row["cancellations"]) == 1
    assert int(row["starting_customers"]) == 5
    assert float(row["churn_rate"]) == 0.2
