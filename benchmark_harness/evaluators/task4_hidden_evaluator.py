from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

EXPECTED_FIXTURE_SHA256 = {
    "fixtures/plan_history.csv": "5c160813026a095905b662b00d52d08d42a2dc9a0bb75dc3148ce7596018673a",
    "fixtures/cancellation_events.csv": "de58bb8286bf1b4706d4d8ef40c93df21c17af028d4ebd446e544586bd38ee33",
}

EXPECTED_ROWS = {
    ("2024-03", "enterprise"): {"cancellations": 5, "starting_customers": 6, "churn_rate": 5 / 6},
    ("2024-03", "pro"): {"cancellations": 0, "starting_customers": 5, "churn_rate": 0.0},
    ("2024-02", "pro"): {"cancellations": 1, "starting_customers": 5, "churn_rate": 0.2},
}

CLAMP_TOKENS = [".clip(", "clip(", "np.minimum", "minimum(", "min(1", "min(1.0"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_fixture_hashes(repo: Path) -> list[str]:
    errors: list[str] = []
    for rel_path, expected_hash in EXPECTED_FIXTURE_SHA256.items():
        path = repo / rel_path
        if not path.exists():
            errors.append(f"missing fixture {rel_path}")
            continue
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            errors.append(f"fixture changed: {rel_path}")
    return errors


def source_appears_to_clamp(repo: Path) -> bool:
    source_path = repo / "src" / "churncalc" / "metrics.py"
    if not source_path.exists():
        return False
    source = source_path.read_text(encoding="utf-8")
    return any(token in source for token in CLAMP_TOKENS)


def _purge_churncalc_modules() -> None:
    """Force imports to come from the repo under evaluation, not a prior test repo."""
    for name in list(sys.modules):
        if name == "churncalc" or name.startswith("churncalc."):
            del sys.modules[name]


def _load_modules(repo: Path):
    src = str(repo / "src")
    _purge_churncalc_modules()
    sys.path.insert(0, src)
    try:
        from churncalc.dashboard_adapter import get_dashboard_churn  # type: ignore
        from churncalc.metrics import calculate_monthly_churn  # type: ignore
    finally:
        try:
            sys.path.remove(src)
        except ValueError:
            pass
    return get_dashboard_churn, calculate_monthly_churn


def _check_expected_rows(churn: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if (churn["churn_rate"] > 1.0).any():
        bad = churn[churn["churn_rate"] > 1.0].to_dict(orient="records")
        errors.append(f"found impossible churn rows: {bad}")
    for (month, plan), expected in EXPECTED_ROWS.items():
        rows = churn[(churn["month"] == month) & (churn["plan"] == plan)]
        if rows.empty:
            errors.append(f"missing expected row: {month} {plan}")
            continue
        actual = rows.iloc[0]
        for column in ["cancellations", "starting_customers"]:
            if int(actual[column]) != int(expected[column]):
                errors.append(f"{month} {plan} {column} expected {expected[column]}, got {actual[column]}")
        if abs(float(actual["churn_rate"]) - float(expected["churn_rate"])) > 1e-9:
            errors.append(f"{month} {plan} churn_rate expected {expected['churn_rate']}, got {actual['churn_rate']}")
    return errors


def _row_value(churn: pd.DataFrame, month: str, plan: str, column: str) -> int:
    rows = churn[(churn["month"] == month) & (churn["plan"] == plan)]
    if rows.empty:
        raise AssertionError(f"missing active-interval synthetic row: {month} {plan}")
    return int(rows.iloc[0][column])


def _check_active_interval_mapping(calculate_monthly_churn) -> list[str]:
    """Check both directions of cancellation-to-plan assignment.

    X001 changes pro -> enterprise before cancellation, so the cancellation belongs
    to enterprise. X002 changes pro -> enterprise after cancellation, so the
    cancellation belongs to pro. This rejects first-plan-wins, last-plan-wins,
    broad merges, broad dedupe, and groupby-nunique-after-bad-merge fixes.
    """
    plan_history = pd.DataFrame(
        [
            {
                "customer_id": "X001",
                "plan": "pro",
                "valid_from": pd.Timestamp("2024-01-01"),
                "valid_to": pd.Timestamp("2024-03-05"),
            },
            {
                "customer_id": "X001",
                "plan": "enterprise",
                "valid_from": pd.Timestamp("2024-03-05"),
                "valid_to": pd.NaT,
            },
            {
                "customer_id": "X002",
                "plan": "pro",
                "valid_from": pd.Timestamp("2024-01-01"),
                "valid_to": pd.Timestamp("2024-03-20"),
            },
            {
                "customer_id": "X002",
                "plan": "enterprise",
                "valid_from": pd.Timestamp("2024-03-20"),
                "valid_to": pd.NaT,
            },
            {
                "customer_id": "X003",
                "plan": "enterprise",
                "valid_from": pd.Timestamp("2024-01-01"),
                "valid_to": pd.NaT,
            },
            {
                "customer_id": "X004",
                "plan": "pro",
                "valid_from": pd.Timestamp("2024-01-01"),
                "valid_to": pd.NaT,
            },
        ]
    )
    cancellations = pd.DataFrame(
        [
            {"customer_id": "X001", "cancelled_at": pd.Timestamp("2024-03-10"), "reason": "after_switch"},
            {"customer_id": "X002", "cancelled_at": pd.Timestamp("2024-03-10"), "reason": "before_later_switch"},
        ]
    )
    churn = calculate_monthly_churn(plan_history, cancellations)

    errors: list[str] = []
    try:
        enterprise_cancellations = _row_value(churn, "2024-03", "enterprise", "cancellations")
        pro_cancellations = _row_value(churn, "2024-03", "pro", "cancellations")
    except AssertionError as exc:
        return [str(exc)]

    if enterprise_cancellations != 1 or pro_cancellations != 1:
        errors.append(
            "active-interval synthetic case expected enterprise cancellations = 1 "
            f"and pro cancellations = 1, got enterprise = {enterprise_cancellations}, "
            f"pro = {pro_cancellations}"
        )
    return errors


def evaluate(repo: Path) -> list[str]:
    repo = repo.resolve()
    errors: list[str] = []
    errors.extend(check_fixture_hashes(repo))
    if source_appears_to_clamp(repo):
        errors.append("metrics.py appears to clamp churn instead of fixing the metric grain")
    try:
        get_dashboard_churn, calculate_monthly_churn = _load_modules(repo)
        churn = get_dashboard_churn(repo / "fixtures")
        errors.extend(_check_expected_rows(churn))
        errors.extend(_check_active_interval_mapping(calculate_monthly_churn))
    except Exception as exc:  # pragma: no cover - evaluator robustness
        errors.append(f"could not evaluate churn: {exc}")
    finally:
        _purge_churncalc_modules()
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hidden evaluator for Task 4 bugfix pilot.")
    parser.add_argument("--repo", required=True, help="Final task repository to evaluate")
    args = parser.parse_args(argv)

    errors = evaluate(Path(args.repo))
    if errors:
        for error in errors:
            print(f"HIDDEN CONTRACT FAILED: {error}", file=sys.stderr)
        return 1
    print("Hidden Task 4 evaluator passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
