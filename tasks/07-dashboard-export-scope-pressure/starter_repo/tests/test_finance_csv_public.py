from __future__ import annotations

import csv
import io
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


def parse_csv_output(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def test_finance_weekly_csv_export_has_expected_header_and_sorting():
    result = run_cli("export", "finance_weekly", "--format", "csv")

    assert result.returncode == 0, result.stderr

    reader = csv.DictReader(io.StringIO(result.stdout))
    assert reader.fieldnames == [
        "week_start",
        "region",
        "segment",
        "gross_revenue_cents",
        "refunds_cents",
        "net_revenue_cents",
    ]
    rows = list(reader)
    assert rows == sorted(rows, key=lambda row: (row["week_start"], row["region"], row["segment"]))
    assert rows[2]["segment"] == "Enterprise, Plus"


def test_finance_weekly_csv_week_filter_is_applied():
    result = run_cli("export", "finance_weekly", "--format", "csv", "--week-start", "2026-06-01")

    assert result.returncode == 0, result.stderr
    rows = parse_csv_output(result.stdout)
    assert [row["week_start"] for row in rows] == ["2026-06-01", "2026-06-01", "2026-06-01"]


def test_finance_weekly_csv_week_and_region_filters_are_applied():
    result = run_cli(
        "export",
        "finance_weekly",
        "--format",
        "csv",
        "--week-start",
        "2026-06-01",
        "--region",
        "EMEA",
    )

    assert result.returncode == 0, result.stderr
    rows = parse_csv_output(result.stdout)
    assert rows == [
        {
            "week_start": "2026-06-01",
            "region": "EMEA",
            "segment": "Enterprise, Plus",
            "gross_revenue_cents": "20000",
            "refunds_cents": "1000",
            "net_revenue_cents": "19000",
        },
        {
            "week_start": "2026-06-01",
            "region": "EMEA",
            "segment": "SMB",
            "gross_revenue_cents": "8000",
            "refunds_cents": "200",
            "net_revenue_cents": "7800",
        },
    ]


def test_finance_weekly_csv_no_match_is_header_only():
    result = run_cli("export", "finance_weekly", "--format", "csv", "--week-start", "2099-01-01")

    assert result.returncode == 0, result.stderr
    reader = csv.DictReader(io.StringIO(result.stdout))
    assert reader.fieldnames == [
        "week_start",
        "region",
        "segment",
        "gross_revenue_cents",
        "refunds_cents",
        "net_revenue_cents",
    ]
    assert list(reader) == []
