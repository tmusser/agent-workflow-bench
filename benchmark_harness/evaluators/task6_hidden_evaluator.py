from __future__ import annotations

import argparse
import importlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

REPORT_COLUMNS = [
    "month",
    "definition_version",
    "eligible_users",
    "activated_users",
    "activation_rate",
]

PRIVATE_USERS_CSV = """user_id,signup_at,user_type,is_test_account,plan_at_signup,current_plan,cancelled_at,region,acquisition_channel
J001,2026-01-05T10:00:00,external,false,trial,trial,,us,organic
J002,2026-01-06T09:00:00,external,false,trial,trial,,us,paid
J003,2026-01-30T12:00:00,external,false,trial,trial,,eu,partner
J004,2025-12-29T08:00:00,external,false,trial,trial,,us,organic
J005,2026-01-08T10:00:00,external,false,trial,trial,,us,paid
J006,2026-01-10T10:00:00,internal,false,trial,trial,,us,internal
J007,2026-01-10T10:00:00,external,false,trial,trial,,us,organic
J008,2026-01-11T10:00:00,external,false,trial,trial,2026-01-12T10:00:00,us,paid
J009,2026-01-12T10:00:00,external,false,trial,enterprise,,us,partner
J010,2026-01-13T10:00:00,external,false,paid,trial,,us,organic
J011,2026-01-14T10:00:00,external,false,trial,trial,,eu,organic
J012,2026-01-20T10:00:00,external,false,trial,trial,,us,paid
BAD001,not-a-date,external,false,trial,trial,,us,paid
F001,2026-02-01T09:00:00,external,false,trial,trial,,us,organic
F002,2026-02-02T09:00:00,external,false,trial,trial,,us,paid
F003,2026-02-26T09:00:00,external,false,trial,trial,,eu,partner
F005,2026-02-04T09:00:00,external,true,trial,trial,,us,paid
F006,2026-02-05T09:00:00,external,false,trial,trial,,us,organic
F007,2026-02-06T09:00:00,external,false,trial,trial,2026-02-06T12:00:00,us,paid
F008,2026-02-07T09:00:00,external,false,trial,enterprise,,eu,partner
F009,2026-02-15T09:00:00,external,false,trial,trial,,us,organic
"""

PRIVATE_EVENTS_CSV = """event_id,user_id,event_at,event_name,event_source
HJ001,J001,2026-01-07T10:00:00,activation_completed,app
HJ002,J002,2026-01-20T09:00:00,activation_completed,app
HJ003,J003,2026-02-03T09:00:00,activation_completed,app
HJ004,J004,2026-01-03T08:00:00,activation_completed,app
HJ005A,J005,2026-01-09T10:00:00,activation_completed,app
HJ005B,J005,2026-01-10T10:00:00,activation_completed,app
HJ006,J006,2026-01-10T10:00:00,activation_completed,app
HJ007,J007,2026-01-01T10:00:00,activation_completed,app
HJ008,J008,2026-01-13T10:00:00,activation_completed,app
HJ009P,J009,2026-01-12T12:00:00,plan_changed,billing
HJ009,J009,2026-01-13T10:00:00,activation_completed,app
HJ010,J010,2026-01-14T10:00:00,activation_completed,app
HJ012,J012,2026-01-28T10:00:00,activation_completed,app
HBAD,BAD001,2026-01-05T10:00:00,activation_completed,app
HF001,F001,2026-02-02T09:00:00,activation_completed,app
HF002,F002,2026-02-12T09:00:00,activation_completed,app
HF003,F003,2026-03-02T09:00:00,activation_completed,app
HF005,F005,2026-02-05T09:00:00,activation_completed,app
HF006A,F006,2026-02-06T09:00:00,activation_completed,app
HF006B,F006,2026-02-07T09:00:00,activation_completed,app
HF007,F007,2026-02-07T09:00:00,activation_completed,app
HF008P,F008,2026-02-07T12:00:00,plan_changed,billing
HF008,F008,2026-02-08T09:00:00,activation_completed,app
HF009,F009,2026-02-25T09:00:00,activation_completed,app
"""

EXPECTED_ROWS = {
    ("v1", "2026-01"): {
        "month": "2026-01",
        "definition_version": "v1",
        "eligible_users": 9,
        "activated_users": 5,
        "activation_rate": 0.555556,
    },
    ("v1", "2026-02"): {
        "month": "2026-02",
        "definition_version": "v1",
        "eligible_users": 7,
        "activated_users": 5,
        "activation_rate": 0.714286,
    },
    ("v1", "2026-03"): {
        "month": "2026-03",
        "definition_version": "v1",
        "eligible_users": 0,
        "activated_users": 0,
        "activation_rate": 0.0,
    },
    ("v2", "2026-01"): {
        "month": "2026-01",
        "definition_version": "v2",
        "eligible_users": 9,
        "activated_users": 4,
        "activation_rate": 0.444444,
    },
    ("v2", "2026-02"): {
        "month": "2026-02",
        "definition_version": "v2",
        "eligible_users": 7,
        "activated_users": 4,
        "activation_rate": 0.571429,
    },
    ("v2", "2026-03"): {
        "month": "2026-03",
        "definition_version": "v2",
        "eligible_users": 0,
        "activated_users": 0,
        "activation_rate": 0.0,
    },
}


def _purge_activation_metrics_modules() -> None:
    for name in list(sys.modules):
        if name == "activation_metrics" or name.startswith("activation_metrics."):
            del sys.modules[name]
    importlib.invalidate_caches()


def _write_private_fixtures(root: Path) -> Path:
    fixtures_dir = root / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    (fixtures_dir / "users.csv").write_text(PRIVATE_USERS_CSV, encoding="utf-8")
    (fixtures_dir / "events.csv").write_text(PRIVATE_EVENTS_CSV, encoding="utf-8")
    return fixtures_dir


def _load_private_inputs(fixtures_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    users = pd.read_csv(fixtures_dir / "users.csv")
    users["is_test_account"] = users["is_test_account"].astype(str).str.strip().str.lower().eq("true")
    events = pd.read_csv(fixtures_dir / "events.csv")
    return users, events


def _import_candidate_api(repo: Path):
    src = str(repo / "src")
    _purge_activation_metrics_modules()
    sys.path.insert(0, src)
    try:
        importlib.invalidate_caches()
        from activation_metrics import (  # type: ignore
            build_activation_report,
            compute_activation_rate_v1,
            compute_activation_rate_v2,
        )
        from activation_metrics.load import load_events, load_users  # type: ignore
    finally:
        try:
            sys.path.remove(src)
        except ValueError:
            pass
        importlib.invalidate_caches()
    return build_activation_report, compute_activation_rate_v1, compute_activation_rate_v2, load_users, load_events


def _compare_report(report: pd.DataFrame, expected: dict[str, object], context: str) -> list[str]:
    errors: list[str] = []
    if list(report.columns) != REPORT_COLUMNS:
        errors.append(f"{context}: report columns were {list(report.columns)}, expected {REPORT_COLUMNS}")
        return errors
    if len(report) != 1:
        errors.append(f"{context}: expected one report row, got {len(report)}")
        return errors

    row = report.iloc[0]
    if row["month"] != expected["month"]:
        errors.append(f"{context}: month expected {expected['month']}, got {row['month']}")
    if row["definition_version"] != expected["definition_version"]:
        errors.append(
            f"{context}: definition_version expected {expected['definition_version']}, got {row['definition_version']}"
        )
    if int(row["eligible_users"]) != int(expected["eligible_users"]):
        errors.append(f"{context}: eligible_users expected {expected['eligible_users']}, got {row['eligible_users']}")
    if int(row["activated_users"]) != int(expected["activated_users"]):
        errors.append(
            f"{context}: activated_users expected {expected['activated_users']}, got {row['activated_users']}"
        )
    if abs(float(row["activation_rate"]) - float(expected["activation_rate"])) > 1e-6:
        errors.append(
            f"{context}: activation_rate expected {expected['activation_rate']}, got {row['activation_rate']}"
        )
    return errors


def _run_cli(repo: Path, fixtures_dir: Path, definition: str, month: str, out_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/run_activation_report.py",
            "--data-dir",
            str(fixtures_dir),
            "--definition",
            definition,
            "--month",
            month,
            "--out",
            str(out_path),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=15,
    )


def evaluate(repo: Path) -> list[str]:
    repo = repo.resolve()
    errors: list[str] = []
    _purge_activation_metrics_modules()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            private_root = Path(tmpdir)
            fixtures_dir = _write_private_fixtures(private_root)

            try:
                (
                    build_activation_report,
                    compute_activation_rate_v1,
                    compute_activation_rate_v2,
                    load_users,
                    load_events,
                ) = _import_candidate_api(repo)
            except Exception as exc:  # pragma: no cover - evaluator robustness
                errors.append(f"could not import activation_metrics API: {exc}")
                return errors

            users = load_users(fixtures_dir)
            events = load_events(fixtures_dir)

            for function_name, function in [
                ("compute_activation_rate_v1", compute_activation_rate_v1),
                ("compute_activation_rate_v2", compute_activation_rate_v2),
            ]:
                if not callable(function):
                    errors.append(f"{function_name} must be callable")

            for definition in ("v1", "v2"):
                for month in ("2026-01", "2026-02", "2026-03"):
                    expected = EXPECTED_ROWS[(definition, month)]
                    context = f"{definition} {month} build_activation_report"
                    try:
                        report = build_activation_report(users.copy(), events.copy(), month, definition)
                    except Exception as exc:
                        errors.append(f"{context} failed: {exc}")
                        continue
                    errors.extend(_compare_report(report, expected, context))

            for definition in ("v1", "v2"):
                for month in ("2026-01", "2026-02", "2026-03"):
                    expected = EXPECTED_ROWS[(definition, month)]
                    out_path = private_root / f"{definition}_{month}.csv"
                    try:
                        completed = _run_cli(repo, fixtures_dir, definition, month, out_path)
                    except subprocess.TimeoutExpired:
                        errors.append(f"CLI {definition} {month} timed out after 15s")
                        continue
                    if completed.returncode != 0:
                        message = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
                        errors.append(f"CLI {definition} {month} failed: {message}")
                        continue
                    if not out_path.exists():
                        errors.append(f"CLI {definition} {month} did not write {out_path.name}")
                        continue
                    cli_report = pd.read_csv(out_path)
                    errors.extend(_compare_report(cli_report, expected, f"CLI {definition} {month}"))
    finally:
        _purge_activation_metrics_modules()
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hidden evaluator for Task 6 activation metric migration.")
    parser.add_argument("--repo", required=True, help="Final task repository to evaluate")
    args = parser.parse_args(argv)

    errors = evaluate(Path(args.repo))
    if errors:
        for error in errors:
            print(f"HIDDEN CONTRACT FAILED: {error}", file=sys.stderr)
        return 1
    print("Hidden Task 6 evaluator passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
