from __future__ import annotations

from collections.abc import Callable

from finboard.reports import finance_weekly_rows, ops_daily_rows

ReportLoader = Callable[[str | None], list[dict[str, object]]] | Callable[[], list[dict[str, object]]]

REPORT_LOADERS: dict[str, ReportLoader] = {
    "finance_weekly": finance_weekly_rows,
    "ops_daily": ops_daily_rows,
}


def available_report_ids() -> tuple[str, ...]:
    return tuple(REPORT_LOADERS)


def get_report_rows(report_id: str, week_start: str | None = None) -> list[dict[str, object]]:
    try:
        loader = REPORT_LOADERS[report_id]
    except KeyError as exc:
        raise KeyError(f"unknown report: {report_id}") from exc
    if report_id == "finance_weekly":
        return loader(week_start)  # type: ignore[misc]
    return loader()  # type: ignore[misc]
