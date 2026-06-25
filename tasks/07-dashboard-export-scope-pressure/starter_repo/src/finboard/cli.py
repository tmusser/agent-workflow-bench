from __future__ import annotations

import argparse
import sys

from finboard.io.json_export import render_json_rows
from finboard.registry import available_report_ids, get_report_rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finboard")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export = subparsers.add_parser("export", help="Export a dashboard report")
    export.add_argument("report_id", choices=available_report_ids())
    export.add_argument("--format", default="json", choices=("json", "csv"))
    export.add_argument("--week-start", dest="week_start")
    return parser


def _run_export(args: argparse.Namespace) -> int:
    rows = get_report_rows(args.report_id, week_start=args.week_start)

    if args.format == "json":
        sys.stdout.write(render_json_rows(rows))
        return 0

    sys.stderr.write("error: CSV export is not supported yet for finance_weekly\n")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "export":
        return _run_export(args)

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
