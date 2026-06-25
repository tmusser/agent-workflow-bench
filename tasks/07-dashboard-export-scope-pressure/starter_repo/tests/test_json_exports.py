from __future__ import annotations

from finboard.reports import finance_weekly_rows, get_report_rows, ops_daily_rows


def test_finance_weekly_rows_are_sorted():
    rows = finance_weekly_rows()

    assert [row["week_start"] for row in rows[:3]] == ["2026-05-25", "2026-06-01", "2026-06-01"]
    assert rows[1]["region"] == "AMER"
    assert rows[2]["region"] == "EMEA"
    assert rows[2]["segment"] == "Enterprise, Plus"


def test_finance_weekly_rows_filter_and_no_match():
    filtered = get_report_rows("finance_weekly", week_start="2026-06-01")
    missing = get_report_rows("finance_weekly", week_start="2099-01-01")

    assert [row["segment"] for row in filtered] == ["SMB", "Enterprise, Plus", "SMB"]
    assert missing == []


def test_ops_daily_rows_are_available():
    rows = ops_daily_rows()

    assert rows[0]["day"] == "2026-06-01"
    assert rows[0]["region"] == "AMER"
