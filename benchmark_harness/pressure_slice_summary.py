from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from benchmark_harness import scorecard

PRESSURE_ORDER = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}
ARM_ORDER = {
    "A-baseline": 0,
    "E-ai-engineering-skills": 1,
}
SUMMARY_FIELDS = [
    "task_slug",
    "arm_slug",
    "pressure_level",
    "pressure_seed",
    "pressure_tokens_estimated",
    "estimated_context_utilization",
    "max_context_utilization",
    "verify_result",
    "hidden_result",
    "initial_green",
    "full_resume_green",
    "stripped_resume_green",
    "artifact_mechanism_active",
    "skill_runtime_proof_valid",
    "initial_solution_latency_observable",
    "initial_actual_turns",
    "initial_first_functional_green_turn",
    "initial_first_bench_ready_green_turn",
    "initial_turns_after_first_functional_green",
    "finalizer_total_turns",
    "finalizer_total_wall_seconds",
    "finalizer_total_cost_usd",
]


def _read_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("scorecard JSON must contain a list of rows")
    rows: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _result_label(value: Any) -> str:
    if value is None or value == "not_run":
        return "n/a"
    if value == 0:
        return "pass"
    return "fail"


def _cell(value: Any) -> str:
    if value is None:
        return "?"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).replace("\n", " ").replace("|", r"\|")


def _sort_key(row: dict[str, Any]) -> tuple[int, str, int, str]:
    arm = str(row.get("arm_slug") or "")
    level = str(row.get("pressure_level") or "none")
    return (
        ARM_ORDER.get(arm, 99),
        str(row.get("task_slug") or ""),
        PRESSURE_ORDER.get(level, 99),
        str(row.get("run_id") or ""),
    )


def select_rows(rows: Iterable[dict[str, Any]], task_slug: str | None = None) -> list[dict[str, Any]]:
    selected = []
    for row in rows:
        if task_slug is not None and row.get("task_slug") != task_slug:
            continue
        selected.append(row)
    return sorted(selected, key=_sort_key)


def render_pressure_slice_table(rows: Iterable[dict[str, Any]], task_slug: str | None = None) -> str:
    selected = select_rows(rows, task_slug=task_slug)
    if not selected:
        return "| no rows |"
    headers = SUMMARY_FIELDS
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in selected:
        rendered = []
        for field in headers:
            if field == "verify_result":
                rendered.append(_result_label(row.get("initial_verify_exit")))
            elif field == "hidden_result":
                rendered.append(_result_label(row.get("initial_hidden_exit")))
            else:
                rendered.append(_cell(row.get(field)))
        lines.append("| " + " | ".join(rendered) + " |")
    return "\n".join(lines)


def _load_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.scorecard_json:
        return _read_json(Path(args.scorecard_json))
    if args.bundles:
        return scorecard.score_bundles(args.bundles)
    raise ValueError("provide --scorecard-json or one or more bundle paths")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a compact pressure-slice degradation table.")
    parser.add_argument("bundles", nargs="*", help="One or more scorecard bundle paths")
    parser.add_argument("--scorecard-json", help="Path to a scorecard JSON file")
    parser.add_argument("--task-slug", default=None, help="Optional task slug filter")
    parser.add_argument("--out", default=None, help="Write markdown output to this path")
    args = parser.parse_args(argv)

    rows = _load_rows(args)
    table = render_pressure_slice_table(rows, task_slug=args.task_slug)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(table + "\n", encoding="utf-8")
    print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
