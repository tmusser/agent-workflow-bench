from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV = os.environ.copy()
ENV["PYTHONPATH"] = str(ROOT / "src")


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "finboard.cli", *args],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
        check=False,
    )


def test_finance_weekly_json_export_works():
    result = run_cli("export", "finance_weekly", "--format", "json")

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert rows[0]["week_start"] == "2026-05-25"
    assert rows[0]["region"] == "APAC"
    assert rows[0]["segment"] == "SMB"


def test_finance_weekly_json_week_filter_works():
    result = run_cli("export", "finance_weekly", "--format", "json", "--week-start", "2026-06-01")

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["week_start"] for row in rows] == ["2026-06-01", "2026-06-01", "2026-06-01"]


def test_finance_weekly_json_no_match_returns_empty_list():
    result = run_cli("export", "finance_weekly", "--format", "json", "--week-start", "2099-01-01")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []


def test_ops_daily_json_export_works():
    result = run_cli("export", "ops_daily", "--format", "json")

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert rows[0]["day"] == "2026-06-01"
    assert rows[0]["region"] == "AMER"
