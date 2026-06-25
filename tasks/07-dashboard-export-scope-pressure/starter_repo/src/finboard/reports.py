from __future__ import annotations

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"

FINANCE_COLUMNS = (
    "week_start",
    "region",
    "segment",
    "gross_revenue_cents",
    "refunds_cents",
    "net_revenue_cents",
)

OPS_COLUMNS = (
    "day",
    "region",
    "tickets_opened",
    "tickets_closed",
)


def _load_csv_rows(path: Path, numeric_columns: tuple[str, ...]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for raw_row in csv.DictReader(handle):
            row: dict[str, object] = {}
            for key, value in raw_row.items():
                if key in numeric_columns:
                    row[key] = int(value) if value not in (None, "") else 0
                else:
                    row[key] = value
            rows.append(row)
    return rows


def _sorted_rows(rows: list[dict[str, object]], columns: tuple[str, ...]) -> list[dict[str, object]]:
    return sorted(rows, key=lambda row: tuple(row[column] for column in columns))


def finance_weekly_rows(week_start: str | None = None) -> list[dict[str, object]]:
    rows = _load_csv_rows(DATA_DIR / "finance_weekly.csv", (
        "gross_revenue_cents",
        "refunds_cents",
        "net_revenue_cents",
    ))
    if week_start is not None:
        rows = [row for row in rows if row["week_start"] == week_start]
    return _sorted_rows(rows, ("week_start", "region", "segment"))


def ops_daily_rows() -> list[dict[str, object]]:
    rows = _load_csv_rows(DATA_DIR / "ops_daily.csv", (
        "tickets_opened",
        "tickets_closed",
    ))
    return _sorted_rows(rows, ("day", "region"))


def get_report_rows(report_id: str, week_start: str | None = None) -> list[dict[str, object]]:
    if report_id == "finance_weekly":
        return finance_weekly_rows(week_start)
    if report_id == "ops_daily":
        return ops_daily_rows()
    raise KeyError(f"unknown report: {report_id}")
