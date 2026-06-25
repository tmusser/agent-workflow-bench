from __future__ import annotations

import pandas as pd

REPORT_COLUMNS = [
    "month",
    "definition_version",
    "eligible_users",
    "activated_users",
    "activation_rate",
]


def _month_mask(series: pd.Series, month: str) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m").eq(month)


def _eligible_users(users: pd.DataFrame, month: str) -> pd.DataFrame:
    signup_at = pd.to_datetime(users["signup_at"], errors="coerce")
    if "cancelled_at" in users.columns:
        cancelled_at = pd.to_datetime(users["cancelled_at"], errors="coerce")
    else:
        cancelled_at = pd.Series(pd.NaT, index=users.index)

    mask = (
        users["user_type"].eq("external")
        & ~users["is_test_account"].fillna(False)
        & users["plan_at_signup"].eq("trial")
        & _month_mask(signup_at, month)
    )

    eligible = users.loc[mask, ["user_id"]].copy()
    eligible["signup_at"] = signup_at.loc[mask].to_numpy()
    eligible["cancelled_at"] = cancelled_at.loc[mask].to_numpy()
    return eligible


def compute_activation_rate_v1(users: pd.DataFrame, events: pd.DataFrame, month: str) -> dict[str, object]:
    eligible = _eligible_users(users, month)
    eligible_users = int(len(eligible))

    if eligible_users == 0:
        return {
            "month": month,
            "definition_version": "v1",
            "eligible_users": 0,
            "activated_users": 0,
            "activation_rate": 0.0,
        }

    merged = eligible.merge(events, on="user_id", how="left")
    qualifying = merged[
        merged["event_name"].eq("activation_completed")
        & _month_mask(merged["event_at"], month)
        & (merged["event_at"] >= merged["signup_at"])
        & (merged["cancelled_at"].isna() | (merged["event_at"] < merged["cancelled_at"]))
    ]

    activated_users = int(qualifying["user_id"].nunique())
    activation_rate = round(activated_users / eligible_users, 6)

    return {
        "month": month,
        "definition_version": "v1",
        "eligible_users": eligible_users,
        "activated_users": activated_users,
        "activation_rate": activation_rate,
    }


def compute_activation_rate_v2(users: pd.DataFrame, events: pd.DataFrame, month: str) -> dict[str, object]:
    raise NotImplementedError("v2 activation metric is not implemented yet")
