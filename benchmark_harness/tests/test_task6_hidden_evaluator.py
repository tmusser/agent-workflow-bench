from __future__ import annotations

import importlib
import shutil
import textwrap
from pathlib import Path

from benchmark_harness.evaluators.task6_hidden_evaluator import evaluate

ROOT = Path(__file__).resolve().parents[2]
STARTER = ROOT / "tasks" / "06-activation-metric-migration" / "starter_repo"


COMMON_PREFIX = textwrap.dedent(
    """
    from __future__ import annotations

    import pandas as pd

    REPORT_COLUMNS = [
        "month",
        "definition_version",
        "eligible_users",
        "activated_users",
        "activation_rate",
    ]

    def _prepare(users: pd.DataFrame, events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        users = users.copy()
        events = events.copy()
        users["signup_at"] = pd.to_datetime(users["signup_at"], errors="coerce")
        if "cancelled_at" in users.columns:
            users["cancelled_at"] = pd.to_datetime(users["cancelled_at"], errors="coerce")
        else:
            users["cancelled_at"] = pd.NaT
        users["is_test_account"] = users["is_test_account"].astype(str).str.strip().str.lower().eq("true")
        events["event_at"] = pd.to_datetime(events["event_at"], errors="coerce")
        return users, events

    def _eligible_users(users: pd.DataFrame, month: str, plan_column: str = "plan_at_signup") -> pd.DataFrame:
        return users[
            users["user_type"].eq("external")
            & ~users["is_test_account"].fillna(False)
            & users[plan_column].eq("trial")
            & users["signup_at"].dt.strftime("%Y-%m").eq(month)
        ].copy()

    def _row(month: str, definition_version: str, eligible_users: int, activated_users: int) -> dict[str, object]:
        return {
            "month": month,
            "definition_version": definition_version,
            "eligible_users": eligible_users,
            "activated_users": activated_users,
            "activation_rate": round(activated_users / eligible_users, 6) if eligible_users else 0.0,
        }
    """
)


CORRECT_ACTIVATION_SOURCE = COMMON_PREFIX + textwrap.dedent(
    """
    def compute_activation_rate_v1(users: pd.DataFrame, events: pd.DataFrame, month: str) -> dict[str, object]:
        users, events = _prepare(users, events)
        eligible = _eligible_users(users, month)
        eligible_users = int(len(eligible))
        if eligible_users == 0:
            return _row(month, "v1", 0, 0)

        merged = eligible.merge(events, on="user_id", how="left")
        qualifying = merged[
            merged["event_name"].eq("activation_completed")
            & merged["event_at"].notna()
            & (merged["event_at"] >= merged["signup_at"])
            & (merged["cancelled_at"].isna() | (merged["event_at"] < merged["cancelled_at"]))
            & merged["event_at"].dt.strftime("%Y-%m").eq(month)
        ]
        activated_users = int(qualifying["user_id"].nunique())
        return _row(month, "v1", eligible_users, activated_users)


    def compute_activation_rate_v2(users: pd.DataFrame, events: pd.DataFrame, month: str) -> dict[str, object]:
        users, events = _prepare(users, events)
        eligible = _eligible_users(users, month)
        eligible_users = int(len(eligible))
        if eligible_users == 0:
            return _row(month, "v2", 0, 0)

        merged = eligible.merge(events, on="user_id", how="left")
        qualifying = merged[
            merged["event_name"].eq("activation_completed")
            & merged["event_at"].notna()
            & (merged["event_at"] >= merged["signup_at"])
            & (merged["event_at"] < merged["signup_at"] + pd.Timedelta(days=7))
            & (merged["cancelled_at"].isna() | (merged["event_at"] < merged["cancelled_at"]))
        ]
        activated_users = int(qualifying["user_id"].nunique())
        return _row(month, "v2", eligible_users, activated_users)
    """
)


EVENT_ROW_DENOMINATOR_SOURCE = COMMON_PREFIX + textwrap.dedent(
    """
    def compute_activation_rate_v1(users: pd.DataFrame, events: pd.DataFrame, month: str) -> dict[str, object]:
        users, events = _prepare(users, events)
        eligible = _eligible_users(users, month)
        merged = eligible.merge(events, on="user_id", how="left")
        qualifying = merged[
            merged["event_name"].eq("activation_completed")
            & merged["event_at"].notna()
            & (merged["event_at"] >= merged["signup_at"])
            & (merged["cancelled_at"].isna() | (merged["event_at"] < merged["cancelled_at"]))
            & merged["event_at"].dt.strftime("%Y-%m").eq(month)
        ]
        activated_users = int(qualifying["user_id"].nunique())
        return _row(month, "v1", int(len(eligible)), activated_users)


    def compute_activation_rate_v2(users: pd.DataFrame, events: pd.DataFrame, month: str) -> dict[str, object]:
        users, events = _prepare(users, events)
        eligible = _eligible_users(users, month)
        merged = eligible.merge(events, on="user_id", how="left")
        qualifying = merged[
            merged["event_name"].eq("activation_completed")
            & merged["event_at"].notna()
            & (merged["event_at"] >= merged["signup_at"])
            & (merged["event_at"] < merged["signup_at"] + pd.Timedelta(days=7))
            & (merged["cancelled_at"].isna() | (merged["event_at"] < merged["cancelled_at"]))
            & merged["event_at"].dt.strftime("%Y-%m").eq(month)
        ]
        activated_users = int(qualifying["user_id"].nunique())
        return _row(month, "v2", int(len(qualifying)), activated_users)
    """
)


ACTIVATION_MONTH_DENOMINATOR_SOURCE = COMMON_PREFIX + textwrap.dedent(
    """
    def compute_activation_rate_v1(users: pd.DataFrame, events: pd.DataFrame, month: str) -> dict[str, object]:
        users, events = _prepare(users, events)
        eligible = _eligible_users(users, month)
        merged = eligible.merge(events, on="user_id", how="left")
        qualifying = merged[
            merged["event_name"].eq("activation_completed")
            & merged["event_at"].notna()
            & (merged["event_at"] >= merged["signup_at"])
            & (merged["cancelled_at"].isna() | (merged["event_at"] < merged["cancelled_at"]))
            & merged["event_at"].dt.strftime("%Y-%m").eq(month)
        ]
        activated_users = int(qualifying["user_id"].nunique())
        return _row(month, "v1", int(len(eligible)), activated_users)


    def compute_activation_rate_v2(users: pd.DataFrame, events: pd.DataFrame, month: str) -> dict[str, object]:
        users, events = _prepare(users, events)
        merged = users.merge(events, on="user_id", how="left")
        month_rows = merged[
            merged["event_name"].eq("activation_completed")
            & merged["event_at"].notna()
            & (merged["event_at"] >= merged["signup_at"])
            & (merged["cancelled_at"].isna() | (merged["event_at"] < merged["cancelled_at"]))
            & merged["event_at"].dt.strftime("%Y-%m").eq(month)
            & merged["plan_at_signup"].eq("trial")
            & merged["user_type"].eq("external")
            & ~merged["is_test_account"].fillna(False)
        ]
        activated_users = int(month_rows["user_id"].nunique())
        return _row(month, "v2", activated_users, activated_users)
    """
)


V1_ALIAS_TO_V2_SOURCE = COMMON_PREFIX + textwrap.dedent(
    """
    def compute_activation_rate_v2(users: pd.DataFrame, events: pd.DataFrame, month: str) -> dict[str, object]:
        users, events = _prepare(users, events)
        eligible = _eligible_users(users, month)
        eligible_users = int(len(eligible))
        if eligible_users == 0:
            return _row(month, "v2", 0, 0)

        merged = eligible.merge(events, on="user_id", how="left")
        qualifying = merged[
            merged["event_name"].eq("activation_completed")
            & merged["event_at"].notna()
            & (merged["event_at"] >= merged["signup_at"])
            & (merged["event_at"] < merged["signup_at"] + pd.Timedelta(days=7))
            & (merged["cancelled_at"].isna() | (merged["event_at"] < merged["cancelled_at"]))
        ]
        activated_users = int(qualifying["user_id"].nunique())
        return _row(month, "v2", eligible_users, activated_users)


    def compute_activation_rate_v1(users: pd.DataFrame, events: pd.DataFrame, month: str) -> dict[str, object]:
        return compute_activation_rate_v2(users, events, month)
    """
)


CURRENT_PLAN_DENOMINATOR_SOURCE = COMMON_PREFIX + textwrap.dedent(
    """
    def compute_activation_rate_v1(users: pd.DataFrame, events: pd.DataFrame, month: str) -> dict[str, object]:
        users, events = _prepare(users, events)
        eligible = _eligible_users(users, month, plan_column="current_plan")
        eligible_users = int(len(eligible))
        if eligible_users == 0:
            return _row(month, "v1", 0, 0)

        merged = eligible.merge(events, on="user_id", how="left")
        qualifying = merged[
            merged["event_name"].eq("activation_completed")
            & merged["event_at"].notna()
            & (merged["event_at"] >= merged["signup_at"])
            & (merged["cancelled_at"].isna() | (merged["event_at"] < merged["cancelled_at"]))
            & merged["event_at"].dt.strftime("%Y-%m").eq(month)
        ]
        activated_users = int(qualifying["user_id"].nunique())
        return _row(month, "v1", eligible_users, activated_users)


    def compute_activation_rate_v2(users: pd.DataFrame, events: pd.DataFrame, month: str) -> dict[str, object]:
        users, events = _prepare(users, events)
        eligible = _eligible_users(users, month, plan_column="current_plan")
        eligible_users = int(len(eligible))
        if eligible_users == 0:
            return _row(month, "v2", 0, 0)

        merged = eligible.merge(events, on="user_id", how="left")
        qualifying = merged[
            merged["event_name"].eq("activation_completed")
            & merged["event_at"].notna()
            & (merged["event_at"] >= merged["signup_at"])
            & (merged["event_at"] < merged["signup_at"] + pd.Timedelta(days=7))
            & (merged["cancelled_at"].isna() | (merged["event_at"] < merged["cancelled_at"]))
        ]
        activated_users = int(qualifying["user_id"].nunique())
        return _row(month, "v2", eligible_users, activated_users)
    """
)


def _copy_starter(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(
        STARTER,
        repo,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "outputs"),
    )
    return repo


def _write_activation_module(repo: Path, source: str) -> None:
    (repo / "src" / "activation_metrics" / "activation.py").write_text(source, encoding="utf-8")
    importlib.invalidate_caches()


def _evaluate_copy(tmp_path: Path, source: str) -> list[str]:
    repo = _copy_starter(tmp_path)
    _write_activation_module(repo, source)
    return evaluate(repo)


def test_hidden_evaluator_fails_starter_repo():
    problems = evaluate(STARTER)

    assert problems


def test_hidden_evaluator_rejects_event_row_denominator_fix(tmp_path: Path):
    problems = _evaluate_copy(tmp_path, EVENT_ROW_DENOMINATOR_SOURCE)

    assert problems


def test_hidden_evaluator_rejects_activation_month_denominator_fix(tmp_path: Path):
    problems = _evaluate_copy(tmp_path, ACTIVATION_MONTH_DENOMINATOR_SOURCE)

    assert problems


def test_hidden_evaluator_rejects_v1_alias_to_v2(tmp_path: Path):
    problems = _evaluate_copy(tmp_path, V1_ALIAS_TO_V2_SOURCE)

    assert problems


def test_hidden_evaluator_rejects_current_plan_denominator_fix(tmp_path: Path):
    problems = _evaluate_copy(tmp_path, CURRENT_PLAN_DENOMINATOR_SOURCE)

    assert problems


def test_hidden_evaluator_accepts_correct_user_grain_v1_v2_implementation(tmp_path: Path):
    assert _evaluate_copy(tmp_path, CORRECT_ACTIVATION_SOURCE) == []
