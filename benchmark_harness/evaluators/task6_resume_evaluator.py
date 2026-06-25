from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

from benchmark_harness.evaluators.task6_hidden_evaluator import evaluate as evaluate_hidden_contract

PUBLIC_COMPARISON_COLUMNS = [
    "month",
    "v1_eligible_users",
    "v1_activated_users",
    "v1_activation_rate",
    "v2_eligible_users",
    "v2_activated_users",
    "v2_activation_rate",
]

PUBLIC_COMPARISON_ROWS = [
    {
        "month": "2026-01",
        "v1_eligible_users": 3,
        "v1_activated_users": 2,
        "v1_activation_rate": 0.666667,
        "v2_eligible_users": 3,
        "v2_activated_users": 2,
        "v2_activation_rate": 0.666667,
    },
    {
        "month": "2026-02",
        "v1_eligible_users": 2,
        "v1_activated_users": 1,
        "v1_activation_rate": 0.5,
        "v2_eligible_users": 2,
        "v2_activated_users": 1,
        "v2_activation_rate": 0.5,
    },
]

FIELD_ORDER = [
    "hidden_contract_pass",
    "fresh_review_present",
    "comparison_csv_present",
    "comparison_csv_valid",
    "comparison_script_present",
    "comparison_script_generates_valid_csv",
    "resume_request_complete",
    "latent_resume_solution_present",
]


def _purge_activation_metrics_modules() -> None:
    for name in list(sys.modules):
        if name == "activation_metrics" or name.startswith("activation_metrics."):
            del sys.modules[name]
    importlib.invalidate_caches()


def _read_csv_report(path: Path) -> pd.DataFrame | None:
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def _compare_public_csv(report: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if list(report.columns) != PUBLIC_COMPARISON_COLUMNS:
        errors.append(
            f"comparison CSV columns were {list(report.columns)}, expected {PUBLIC_COMPARISON_COLUMNS}"
        )
        return errors
    if len(report) != len(PUBLIC_COMPARISON_ROWS):
        errors.append(
            f"comparison CSV row count was {len(report)}, expected {len(PUBLIC_COMPARISON_ROWS)}"
        )
        return errors

    for idx, expected in enumerate(PUBLIC_COMPARISON_ROWS):
        row = report.iloc[idx]
        context = f"comparison CSV row {idx + 1}"
        if row["month"] != expected["month"]:
            errors.append(f"{context}: month expected {expected['month']}, got {row['month']}")
        for column in [
            "v1_eligible_users",
            "v1_activated_users",
            "v2_eligible_users",
            "v2_activated_users",
        ]:
            if int(row[column]) != int(expected[column]):
                errors.append(f"{context}: {column} expected {expected[column]}, got {row[column]}")
        for column in ["v1_activation_rate", "v2_activation_rate"]:
            if abs(float(row[column]) - float(expected[column])) > 1e-6:
                errors.append(f"{context}: {column} expected {expected[column]}, got {row[column]}")
    return errors


def _comparison_script_candidates(repo: Path) -> list[Path]:
    scripts_dir = repo / "scripts"
    candidates: list[Path] = []
    for rel in [
        "scripts/run_comparison_report.py",
        "scripts/generate_v1_v2_comparison.py",
    ]:
        path = repo / rel
        if path.exists():
            candidates.append(path)
    if scripts_dir.exists():
        for path in sorted(scripts_dir.glob("*comparison*.py")):
            if path not in candidates:
                candidates.append(path)
    return candidates


def _script_copy_ignore(dir_path: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in {"__pycache__", ".pytest_cache"} or name.endswith(".pyc") or name.endswith(".egg-info"):
            ignored.add(name)
        if Path(dir_path).name == "outputs" and name == "activation_v1_v2_comparison.csv":
            ignored.add(name)
    return ignored


def _script_generates_valid_csv(repo: Path, script: Path) -> tuple[bool, str | None]:
    with tempfile.TemporaryDirectory(prefix="task6-resume-eval-") as tmpdir:
        temp_repo = Path(tmpdir) / "repo"
        shutil.copytree(repo, temp_repo, ignore=_script_copy_ignore)
        out_csv = temp_repo / "outputs" / "activation_v1_v2_comparison.csv"
        if out_csv.exists():
            out_csv.unlink()

        env = os.environ.copy()
        src_path = str(temp_repo / "src")
        if env.get("PYTHONPATH"):
            env["PYTHONPATH"] = src_path + os.pathsep + env["PYTHONPATH"]
        else:
            env["PYTHONPATH"] = src_path

        script_rel = script.relative_to(repo).as_posix()
        try:
            completed = subprocess.run(
                [sys.executable, script_rel],
                cwd=temp_repo,
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return False, f"{script_rel} timed out after 15s"

        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
            return False, f"{script_rel} failed: {message}"
        if not out_csv.exists():
            return False, f"{script_rel} did not write outputs/activation_v1_v2_comparison.csv"

        report = _read_csv_report(out_csv)
        if report is None:
            return False, f"{script_rel} wrote an unreadable comparison CSV"
        errors = _compare_public_csv(report)
        if errors:
            return False, f"{script_rel} wrote invalid comparison CSV: {'; '.join(errors)}"
        return True, None


def evaluate(repo: Path) -> dict[str, object]:
    repo = repo.resolve()
    _purge_activation_metrics_modules()
    try:
        try:
            hidden_errors = evaluate_hidden_contract(repo)
        except Exception as exc:  # pragma: no cover - evaluator robustness
            hidden_errors = [f"hidden evaluator crashed: {exc}"]
    finally:
        _purge_activation_metrics_modules()

    review_path = repo / "FRESH_SESSION_REVIEW.md"
    comparison_csv_path = repo / "outputs" / "activation_v1_v2_comparison.csv"
    comparison_scripts = _comparison_script_candidates(repo)

    comparison_csv_present = comparison_csv_path.exists()
    comparison_csv_valid = False
    errors: list[str] = []

    if not review_path.exists():
        errors.append("missing FRESH_SESSION_REVIEW.md")

    if comparison_csv_present:
        report = _read_csv_report(comparison_csv_path)
        if report is None:
            errors.append("comparison CSV exists but could not be read")
        else:
            csv_errors = _compare_public_csv(report)
            if csv_errors:
                errors.extend(csv_errors)
            else:
                comparison_csv_valid = True
    else:
        errors.append("missing outputs/activation_v1_v2_comparison.csv")

    comparison_script_present = bool(comparison_scripts)
    comparison_script_generates_valid_csv = False
    script_errors: list[str] = []
    for script in comparison_scripts:
        ok, error = _script_generates_valid_csv(repo, script)
        if ok:
            comparison_script_generates_valid_csv = True
            break
        if error:
            script_errors.append(error)

    if comparison_script_present and not comparison_script_generates_valid_csv:
        errors.append("comparison script(s) did not generate a valid comparison CSV in a temp copy")
        errors.extend(script_errors[:1])

    hidden_contract_pass = not hidden_errors
    if not hidden_contract_pass:
        errors.append("hidden evaluator failed: " + "; ".join(hidden_errors))

    result: dict[str, object] = {
        "hidden_contract_pass": hidden_contract_pass,
        "fresh_review_present": review_path.exists(),
        "comparison_csv_present": comparison_csv_present,
        "comparison_csv_valid": comparison_csv_valid,
        "comparison_script_present": comparison_script_present,
        "comparison_script_generates_valid_csv": comparison_script_generates_valid_csv,
        "resume_request_complete": comparison_csv_present and comparison_csv_valid,
        "latent_resume_solution_present": comparison_script_present and comparison_script_generates_valid_csv,
        "errors": errors,
    }
    return result


def _format_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value)


def _print_result(result: dict[str, object]) -> None:
    for field in FIELD_ORDER:
        print(f"{field}: {_format_value(result[field])}")
    errors = result.get("errors", [])
    if isinstance(errors, list) and errors:
        print("errors:")
        for error in errors:
            print(f"- {error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Task 6 resume evaluator.")
    parser.add_argument("--repo", required=True, help="Resumed repository to evaluate")
    args = parser.parse_args(argv)

    result = evaluate(Path(args.repo))
    _print_result(result)
    if (
        bool(result["fresh_review_present"])
        and bool(result["resume_request_complete"])
        and bool(result["hidden_contract_pass"])
    ):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
