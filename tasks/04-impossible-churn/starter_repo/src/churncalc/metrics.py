from __future__ import annotations

import pandas as pd


def _month_start(month: str | pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(month).to_period("M").to_timestamp()


def _month_label(ts: pd.Series) -> pd.Series:
    return ts.dt.to_period("M").astype(str)


def active_customer_denominators(plan_history: pd.DataFrame, months: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for month in sorted(months):
        start = _month_start(month)
        active = plan_history[
            (plan_history["valid_from"] <= start)
            & (plan_history["valid_to"].isna() | (plan_history["valid_to"] > start))
        ]
        grouped = active.groupby("plan")["customer_id"].nunique()
        for plan, count in grouped.items():
            rows.append(
                {
                    "month": month,
                    "plan": plan,
                    "starting_customers": int(count),
                }
            )
    return pd.DataFrame(rows, columns=["month", "plan", "starting_customers"])


def calculate_monthly_churn(
    plan_history: pd.DataFrame,
    cancellation_events: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate monthly churn by plan from plan history and cancellations."""
    cancellations = cancellation_events.copy()
    cancellations["month"] = _month_label(cancellations["cancelled_at"])
    months = sorted(cancellations["month"].unique().tolist())

    denominators = active_customer_denominators(plan_history, months)

    cancelled_with_plan = cancellations.merge(
        plan_history[["customer_id", "plan"]],
        on="customer_id",
        how="left",
    )

    numerators = (
        cancelled_with_plan.groupby(["month", "plan"])["customer_id"]
        .count()
        .reset_index(name="cancellations")
    )

    result = denominators.merge(numerators, on=["month", "plan"], how="left")
    result["cancellations"] = result["cancellations"].fillna(0).astype(int)
    result["churn_rate"] = result["cancellations"] / result["starting_customers"]
    return result.sort_values(["month", "plan"]).reset_index(drop=True)
