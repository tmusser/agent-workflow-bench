from __future__ import annotations

import shutil
from pathlib import Path

from benchmark_harness.evaluators.task4_hidden_evaluator import evaluate

ROOT = Path(__file__).resolve().parents[2]
STARTER = ROOT / "tasks" / "04-impossible-churn" / "starter_repo"

LATEST_PLAN_WINS_METRICS = r'''
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
            rows.append({"month": month, "plan": plan, "starting_customers": int(count)})
    return pd.DataFrame(rows, columns=["month", "plan", "starting_customers"])


def calculate_monthly_churn(plan_history: pd.DataFrame, cancellation_events: pd.DataFrame) -> pd.DataFrame:
    cancellations = cancellation_events.copy()
    cancellations["month"] = _month_label(cancellations["cancelled_at"])
    months = sorted(cancellations["month"].unique().tolist())
    denominators = active_customer_denominators(plan_history, months)

    # Deliberately wrong: assigns every cancellation to the customer's latest
    # plan overall instead of the plan active at cancelled_at.
    latest_plan = (
        plan_history.sort_values("valid_from")
        .drop_duplicates("customer_id", keep="last")[["customer_id", "plan"]]
    )
    cancelled_with_plan = cancellations.merge(latest_plan, on="customer_id", how="left")
    numerators = (
        cancelled_with_plan.groupby(["month", "plan"])["customer_id"]
        .nunique()
        .reset_index(name="cancellations")
    )

    result = denominators.merge(numerators, on=["month", "plan"], how="left")
    result["cancellations"] = result["cancellations"].fillna(0).astype(int)
    result["churn_rate"] = result["cancellations"] / result["starting_customers"]
    return result.sort_values(["month", "plan"]).reset_index(drop=True)
'''

FIRST_PLAN_WINS_METRICS = LATEST_PLAN_WINS_METRICS.replace(
    'drop_duplicates("customer_id", keep="last")',
    'drop_duplicates("customer_id", keep="first")',
).replace(
    "latest_plan = (",
    "first_plan = (",
).replace(
    'cancelled_with_plan = cancellations.merge(latest_plan, on="customer_id", how="left")',
    'cancelled_with_plan = cancellations.merge(first_plan, on="customer_id", how="left")',
).replace(
    "the customer's latest",
    "the customer's first",
)

CORRECT_ACTIVE_INTERVAL_METRICS = r'''
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
            rows.append({"month": month, "plan": plan, "starting_customers": int(count)})
    return pd.DataFrame(rows, columns=["month", "plan", "starting_customers"])


def calculate_monthly_churn(plan_history: pd.DataFrame, cancellation_events: pd.DataFrame) -> pd.DataFrame:
    cancellations = cancellation_events.copy()
    cancellations["month"] = _month_label(cancellations["cancelled_at"])
    months = sorted(cancellations["month"].unique().tolist())
    denominators = active_customer_denominators(plan_history, months)

    merged = cancellations.merge(plan_history, on="customer_id", how="left")
    active = merged[
        (merged["valid_from"] <= merged["cancelled_at"])
        & (merged["valid_to"].isna() | (merged["cancelled_at"] < merged["valid_to"]))
    ]
    numerators = (
        active.groupby(["month", "plan"])["customer_id"]
        .nunique()
        .reset_index(name="cancellations")
    )

    result = denominators.merge(numerators, on=["month", "plan"], how="left")
    result["cancellations"] = result["cancellations"].fillna(0).astype(int)
    result["churn_rate"] = result["cancellations"] / result["starting_customers"]
    return result.sort_values(["month", "plan"]).reset_index(drop=True)
'''


def _copy_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(STARTER, repo)
    return repo


def _write_metrics(repo: Path, source: str) -> None:
    (repo / "src" / "churncalc" / "metrics.py").write_text(source, encoding="utf-8")


def test_hidden_evaluator_fails_starter_repo():
    problems = evaluate(STARTER)

    assert any("impossible churn" in problem or "expected" in problem for problem in problems)


def test_hidden_evaluator_rejects_fixture_tampering(tmp_path: Path):
    repo = _copy_repo(tmp_path)
    fixture = repo / "fixtures" / "cancellation_events.csv"
    fixture.write_text("customer_id,cancelled_at,reason\n", encoding="utf-8")

    problems = evaluate(repo)

    assert any("fixture changed" in problem for problem in problems)


def test_hidden_evaluator_rejects_last_plan_wins_fix(tmp_path: Path):
    repo = _copy_repo(tmp_path)
    _write_metrics(repo, LATEST_PLAN_WINS_METRICS)

    problems = evaluate(repo)

    assert any("active-interval synthetic case" in problem for problem in problems)


def test_hidden_evaluator_rejects_first_plan_wins_fix(tmp_path: Path):
    repo = _copy_repo(tmp_path)
    _write_metrics(repo, FIRST_PLAN_WINS_METRICS)

    problems = evaluate(repo)

    assert any("active-interval synthetic case" in problem for problem in problems)


def test_hidden_evaluator_accepts_active_interval_fix_after_prior_import(tmp_path: Path):
    # Evaluate the starter first so churncalc modules are imported from one repo.
    # The hidden evaluator must purge module cache before evaluating this temp repo.
    assert evaluate(STARTER)

    repo = _copy_repo(tmp_path)
    _write_metrics(repo, CORRECT_ACTIVE_INTERVAL_METRICS)

    assert evaluate(repo) == []


def test_starter_repo_has_gitignore_for_run_workspace_noise():
    gitignore = (STARTER / ".gitignore").read_text(encoding="utf-8")

    for pattern in [".venv/", "__pycache__/", ".pytest_cache/", "*.egg-info/"]:
        assert pattern in gitignore
