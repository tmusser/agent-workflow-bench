from __future__ import annotations

import argparse
import csv
import fnmatch
import io
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from benchmark_harness.skill_runtime_recovery import arm_requires_skill_runtime
from benchmark_harness.summarize_run_effort import load_run_metrics
from benchmark_harness.task_catalog import TASKS, resolve_defaults

SCHEMA_VERSION = 1
PHASE_INITIAL = "initial"
PHASE_FULL_RESUME = "full_resume"
PHASE_STRIPPED_RESUME = "stripped_resume"

BLOCKED_PUBLIC_PREFIX = "blocked:"
BLOCKED_CLASSIFICATIONS = {
    "agent_stopped_before_attempt",
    "environment_blocked_before_attempt",
    "usage_limit_blocked_before_attempt",
}
FAILED_CLASSIFICATIONS = {
    "artifact_contract_failure",
    "functional_failure",
    "missing_skill_runtime_proof",
}

DEFAULT_OUTPUT_CSV = Path("benchmark-data/codex_matrix_metrics.csv")
DEFAULT_OUTPUT_MD = Path("benchmark-data/codex_matrix_metrics.md")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _split_values(values: Iterable[str] | None) -> list[str]:
    flattened: list[str] = []
    if not values:
        return flattened
    for value in values:
        for item in str(value).split(","):
            item = item.strip()
            if item:
                flattened.append(item)
    return flattened


def _canonical_phase(value: object) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None
    normalized = text.lower().replace("-", "_").replace(" ", "_")
    if normalized == "initial":
        return PHASE_INITIAL
    if normalized in {"full", "full_resume", "fullresume"}:
        return PHASE_FULL_RESUME
    if normalized in {"stripped", "stripped_resume", "strippedresume"}:
        return PHASE_STRIPPED_RESUME
    return normalized or None


def _phase_from_path(path: Path) -> str:
    name = path.parent.name
    if name.endswith("_full"):
        return PHASE_FULL_RESUME
    if name.endswith("_stripped"):
        return PHASE_STRIPPED_RESUME
    return PHASE_INITIAL


def _infer_task_slug(run_id: str) -> str | None:
    for task_slug, config in TASKS.items():
        if run_id.startswith(config.run_prefix):
            return task_slug
    return None


def _arm_code(arm_slug: str) -> str:
    return arm_slug.split("-", 1)[0]


def _infer_arm_slug(run_id: str, task_slug: str | None, selected_arms: set[str]) -> str | None:
    if task_slug is None:
        return None
    config = TASKS.get(task_slug)
    if config is None:
        return None
    prefix = config.run_prefix + "_"
    if not run_id.startswith(prefix):
        return None
    suffix = run_id[len(prefix) :]
    arm_code = suffix.split("_", 1)[0]
    if not arm_code:
        return None

    exact_matches = [arm_slug for arm_slug in selected_arms if _arm_code(arm_slug) == arm_code]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        return None

    for arm_slug in selected_arms:
        if arm_slug.startswith(f"{arm_code}-"):
            return arm_slug
    return None


def _infer_base_run_id(run_id: str, path: Path) -> str:
    name = path.parent.name
    if name.endswith("_full"):
        return name[: -len("_full")]
    if name.endswith("_stripped"):
        return name[: -len("_stripped")]
    return run_id


def _infer_provider(arm_slug: str | None, metrics: Mapping[str, Any]) -> str | None:
    provider = _normalize_text(metrics.get("provider"))
    if provider:
        return provider
    if arm_slug and arm_slug.startswith("C-"):
        return "codex"
    if arm_slug and arm_slug.startswith("E-"):
        return "claude"
    return None


def _infer_runner(provider: str | None, metrics: Mapping[str, Any]) -> str | None:
    runner = _normalize_text(metrics.get("runner"))
    if runner:
        return runner
    if provider == "codex":
        return "codex-cli"
    if provider == "claude":
        return "claude-cli"
    return None


def _safe_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: object) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    text = _normalize_text(value).lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def _safe_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _first_positive_int(data: Mapping[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        parsed = _safe_int(data.get(key))
        if parsed is not None:
            return max(parsed, 0)
    return None


def _canonical_input_tokens(data: Mapping[str, Any]) -> int | None:
    for key in ("input_tokens", "total_input_tokens", "prompt_tokens"):
        parsed = _safe_int(data.get(key))
        if parsed is not None:
            return max(parsed, 0)

    usage_input_tokens = _safe_int(data.get("usage_input_tokens"))
    if usage_input_tokens is None:
        return None

    total = max(usage_input_tokens, 0)
    for key in ("usage_cache_creation_input_tokens", "usage_cache_read_input_tokens"):
        extra = _safe_int(data.get(key))
        if extra is not None:
            total += max(extra, 0)
    return total


def _canonical_cached_input_tokens(data: Mapping[str, Any]) -> int | None:
    return _first_positive_int(
        data,
        (
            "cached_input_tokens",
            "usage_cache_read_input_tokens",
            "cache_read_input_tokens",
            "prompt_cache_hit_tokens",
        ),
    )


def _canonical_output_tokens(data: Mapping[str, Any]) -> int | None:
    return _first_positive_int(
        data,
        (
            "output_tokens",
            "total_output_tokens",
            "usage_output_tokens",
            "completion_tokens",
        ),
    )


def _canonical_reasoning_output_tokens(data: Mapping[str, Any]) -> int | None:
    return _first_positive_int(
        data,
        (
            "reasoning_output_tokens",
            "reasoning_tokens",
        ),
    )


def _canonical_wall_clock_seconds(data: Mapping[str, Any]) -> float | None:
    value = _safe_float(data.get("wall_clock_seconds"))
    if value is not None:
        return round(value, 3)
    value = _safe_float(data.get("wall_seconds"))
    if value is not None:
        return round(value, 3)
    value = _safe_float(data.get("duration_seconds"))
    if value is not None:
        return round(value, 3)
    value = _safe_float(data.get("duration_ms"))
    if value is not None:
        return round(value / 1000.0, 3)
    value = _safe_float(data.get("duration_api_ms"))
    if value is not None:
        return round(value / 1000.0, 3)
    return None


def _canonical_total_tokens(
    data: Mapping[str, Any],
    *,
    input_tokens: int | None,
    output_tokens: int | None,
) -> int | None:
    total = _first_positive_int(data, ("total_tokens",))
    if total is not None:
        return total
    parts = [value for value in (input_tokens, output_tokens) if value is not None]
    if parts:
        return sum(parts)
    return None


def canonical_token_fields(data: Mapping[str, Any]) -> dict[str, int | None]:
    input_tokens = _canonical_input_tokens(data)
    cached_input_tokens = _canonical_cached_input_tokens(data)
    output_tokens = _canonical_output_tokens(data)
    reasoning_output_tokens = _canonical_reasoning_output_tokens(data)
    total_tokens = _canonical_total_tokens(
        data,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    uncached_input_tokens = None
    if input_tokens is not None:
        if cached_input_tokens is None:
            uncached_input_tokens = input_tokens
        else:
            uncached_input_tokens = max(input_tokens - cached_input_tokens, 0)
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "uncached_input_tokens": uncached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
        "total_tokens": total_tokens,
    }


def _wall_billableish_tokens(row: Mapping[str, Any]) -> int | None:
    uncached = row.get("uncached_input_tokens")
    output = row.get("output_tokens")
    if isinstance(uncached, int) and isinstance(output, int):
        return uncached + output
    return None


def _metrics_time_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _status_from_recovery(run_dir: Path, *, arm_slug: str) -> str:
    recovery = _read_json(run_dir / "skill_runtime_recovery.json")
    if not recovery:
        return "completed"
    public_status = _normalize_text(recovery.get("public_status")).lower()
    classification = _normalize_text(recovery.get("classification")).lower()
    functional_green = _coerce_bool(recovery.get("functional_green"))
    if functional_green is None:
        verify_exit = _safe_int(recovery.get("verification_exit"))
        hidden_exit = _safe_int(recovery.get("hidden_evaluator_exit"))
        if verify_exit is not None and hidden_exit is not None:
            functional_green = verify_exit == 0 and hidden_exit == 0

    skill_runtime_required = arm_requires_skill_runtime(arm_slug)

    if public_status.startswith(BLOCKED_PUBLIC_PREFIX):
        if classification == "skill_context_failure" and not skill_runtime_required:
            pass
        else:
            return "blocked"

    if classification in BLOCKED_CLASSIFICATIONS:
        return "blocked"
    # Older C-arm recovery files can mislabel real task outcomes as skill-context
    # failures; use the functional evidence instead of preserving that stale block.
    if classification == "skill_context_failure":
        if skill_runtime_required:
            return "blocked"
        if functional_green is True:
            return "completed"
        if functional_green is False:
            return "failed"
        return "failed"
    if classification in FAILED_CLASSIFICATIONS:
        return "failed"
    if functional_green is True:
        return "completed"
    if functional_green is False:
        return "failed"
    return "completed"


def _relative_or_text(path: Path, value: object) -> str:
    text = _normalize_text(value)
    if text:
        return text
    try:
        return str(path.relative_to(path.parents[1]))
    except ValueError:
        return str(path)


def _relative_path(repo_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _discover_metrics_paths(repo_root: Path) -> list[Path]:
    roots = [repo_root / "benchmark-data" / "runs", repo_root / "benchmark-data" / "resume-runs"]
    discovered: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        discovered.extend(sorted(root.glob("*/run_metrics.json")))
    return discovered


def _load_summary_expectations(summary_csv: Path) -> list[tuple[str, str, str, str | None]]:
    rows: list[tuple[str, str, str, str | None]] = []
    try:
        with summary_csv.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw_row in reader:
                task_slug = _normalize_text(raw_row.get("task_slug") or raw_row.get("task"))
                arm_slug = _normalize_text(raw_row.get("arm_slug") or raw_row.get("arm"))
                phase = _canonical_phase(raw_row.get("phase") or raw_row.get("label"))
                if not task_slug or not arm_slug or not phase:
                    continue
                expected_run_id = _normalize_text(raw_row.get("expected_run_id") or raw_row.get("run_id")) or None
                rows.append((task_slug, arm_slug, phase, expected_run_id))
    except OSError:
        return []
    return rows


def _expected_rows_from_explicit(
    tasks: list[str],
    arms: list[str],
    phases: list[str],
) -> list[tuple[str, str, str, str | None]]:
    expectations: list[tuple[str, str, str, str | None]] = []
    for task_slug in tasks:
        for arm_slug in arms:
            defaults = resolve_defaults(task_slug, arm_slug)
            for phase in phases:
                expected_run_id = f"{defaults['RUN_PREFIX_DEFAULT']}_{_arm_code(arm_slug)}_r1"
                expectations.append((task_slug, arm_slug, phase, expected_run_id))
    return expectations


def _normalize_selected_row(
    path: Path,
    metrics: Mapping[str, Any],
    *,
    repo_root: Path,
    selected_arms: set[str],
    run_id_globs: list[str],
) -> dict[str, Any] | None:
    run_id = _normalize_text(metrics.get("run_id")) or path.parent.name
    if run_id_globs and not any(fnmatch.fnmatch(run_id, pattern) or fnmatch.fnmatch(path.as_posix(), pattern) for pattern in run_id_globs):
        return None

    task_slug = _normalize_text(metrics.get("task_slug")) or _infer_task_slug(run_id)
    arm_slug = _normalize_text(metrics.get("arm_slug")) or _infer_arm_slug(run_id, task_slug, selected_arms)
    if not task_slug or not arm_slug or arm_slug not in selected_arms:
        return None

    phase = _canonical_phase(metrics.get("phase")) or _canonical_phase(metrics.get("label")) or _phase_from_path(path)
    base_run_id = _normalize_text(metrics.get("base_run_id")) or _infer_base_run_id(run_id, path)
    provider = _infer_provider(arm_slug, metrics)
    runner = _infer_runner(provider, metrics)
    model_label = _normalize_text(metrics.get("model_label") or metrics.get("model"))
    token_fields = canonical_token_fields(metrics)

    actual_turns = _first_positive_int(metrics, ("actual_turns", "num_turns", "turns"))
    wall_clock_seconds = _canonical_wall_clock_seconds(metrics)
    exit_code = _first_positive_int(
        metrics,
        (
            "exit_code",
            "runner_exit_code",
            "agent_exit_code",
            "claude_exit_code",
            "codex_exit_code",
        ),
    )
    run_dir = path.parent
    status = _status_from_recovery(run_dir, arm_slug=arm_slug)
    selected = {
        "task_slug": task_slug,
        "arm_slug": arm_slug,
        "phase": phase,
        "run_id": run_id,
        "base_run_id": base_run_id,
        "provider": provider or "",
        "runner": runner or "",
        "model_label": model_label,
        "status": status,
        "found": True,
        "blocked": False,
        "row_state": status,
        "actual_turns": actual_turns,
        "input_tokens": token_fields["input_tokens"],
        "cached_input_tokens": token_fields["cached_input_tokens"],
        "uncached_input_tokens": token_fields["uncached_input_tokens"],
        "output_tokens": token_fields["output_tokens"],
        "reasoning_output_tokens": token_fields["reasoning_output_tokens"],
        "billableish_tokens": None,
        "wall_clock_seconds": wall_clock_seconds,
        "exit_code": exit_code,
        "metrics_path": _relative_path(repo_root, path),
        "trace_summary_path": _normalize_text(metrics.get("trace_summary_path")) or str(run_dir / "agent_turn_trace_summary.json"),
        "stdout_path": _normalize_text(metrics.get("stdout_path")),
        "stderr_path": _normalize_text(metrics.get("stderr_path")),
        "_mtime_ns": _metrics_time_ns(path),
        "_selected_by": "metrics",
    }
    selected["billableish_tokens"] = _wall_billableish_tokens(selected)
    selected["blocked"] = selected["status"] == "blocked"
    return selected


def _selected_cell_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(row["task_slug"]), str(row["arm_slug"]), str(row["phase"]))


def _choose_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        candidates,
        key=lambda row: (
            row.get("_mtime_ns", 0),
            row.get("run_id", ""),
            row.get("metrics_path", ""),
        ),
    )[-1]


def _rows_from_discovery(
    repo_root: Path,
    *,
    selected_arms: set[str],
    run_id_globs: list[str],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    discovered = _discover_metrics_paths(repo_root)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for path in discovered:
        metrics = load_run_metrics(path)
        if not metrics:
            continue
        row = _normalize_selected_row(
            path,
            metrics,
            repo_root=repo_root,
            selected_arms=selected_arms,
            run_id_globs=run_id_globs,
        )
        if row is None:
            continue
        grouped[_selected_cell_key(row)].append(row)

    selected_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for key, candidates in grouped.items():
        selected_rows[key] = _choose_candidate(candidates)
    return selected_rows


def _apply_expected_filters(
    expected_rows: list[tuple[str, str, str, str | None]],
    *,
    task_filter: set[str],
    arm_filter: set[str],
    phase_filter: set[str],
) -> list[tuple[str, str, str, str | None]]:
    filtered: list[tuple[str, str, str, str | None]] = []
    for task_slug, arm_slug, phase, expected_run_id in expected_rows:
        if task_filter and task_slug not in task_filter:
            continue
        if arm_filter and arm_slug not in arm_filter:
            continue
        if phase_filter and phase not in phase_filter:
            continue
        filtered.append((task_slug, arm_slug, phase, expected_run_id))
    return filtered


def summarize_matrix(
    *,
    repo_root: Path,
    tasks: list[str],
    arms: list[str],
    phases: list[str],
    summary_csv: Path | None = None,
    run_id_globs: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    run_id_globs = run_id_globs or []
    task_filter = set(tasks)
    arm_filter = set(arms)
    phase_filter = set(phases)

    if summary_csv is not None:
        expected_rows = _load_summary_expectations(summary_csv)
    else:
        if not tasks or not arms:
            raise ValueError("either --summary-csv or both --task and --arm must be supplied")
        expected_rows = _expected_rows_from_explicit(tasks, arms, phases)

    expected_rows = _apply_expected_filters(
        expected_rows,
        task_filter=task_filter if summary_csv is not None else set(),
        arm_filter=arm_filter if summary_csv is not None else set(),
        phase_filter=phase_filter if summary_csv is not None else set(),
    )

    selected_rows = _rows_from_discovery(repo_root, selected_arms=arm_filter or {arm for _, arm, _, _ in expected_rows}, run_id_globs=run_id_globs)

    rows: list[dict[str, Any]] = []
    totals = {
        "schema_version": SCHEMA_VERSION,
        "scheduled_rows": len(expected_rows),
        "rows_found": 0,
        "rows_missing": 0,
        "valid_completed_rows": 0,
        "failed_rows": 0,
        "blocked_rows": 0,
        "actual_turns": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "uncached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "billableish_tokens": 0,
        "wall_clock_seconds": 0.0,
    }

    for task_slug, arm_slug, phase, expected_run_id in expected_rows:
        key = (task_slug, arm_slug, phase)
        selected = selected_rows.get(key)
        if selected is None:
            rows.append(
                {
                    "task_slug": task_slug,
                    "arm_slug": arm_slug,
                    "phase": phase,
                    "expected_run_id": expected_run_id or f"{resolve_defaults(task_slug, arm_slug)['RUN_PREFIX_DEFAULT']}_{_arm_code(arm_slug)}_r1",
                    "run_id": "",
                    "base_run_id": "",
                    "provider": "codex" if arm_slug.startswith("C-") else "claude" if arm_slug.startswith("E-") else "",
                    "runner": "codex-cli" if arm_slug.startswith("C-") else "claude-cli" if arm_slug.startswith("E-") else "",
                    "model_label": "",
                    "status": "missing",
                    "found": False,
                    "blocked": False,
                    "row_state": "missing",
                    "actual_turns": "",
                    "input_tokens": "",
                    "cached_input_tokens": "",
                    "uncached_input_tokens": "",
                    "output_tokens": "",
                    "reasoning_output_tokens": "",
                    "billableish_tokens": "",
                    "wall_clock_seconds": "",
                    "exit_code": "",
                    "metrics_path": "",
                    "trace_summary_path": "",
                    "stdout_path": "",
                    "stderr_path": "",
                }
            )
            continue

        row = {
            "task_slug": selected["task_slug"],
            "arm_slug": selected["arm_slug"],
            "phase": selected["phase"],
            "expected_run_id": expected_run_id or f"{resolve_defaults(task_slug, arm_slug)['RUN_PREFIX_DEFAULT']}_{_arm_code(arm_slug)}_r1",
            "run_id": selected["run_id"],
            "base_run_id": selected["base_run_id"],
            "provider": selected["provider"],
            "runner": selected["runner"],
            "model_label": selected["model_label"],
            "status": selected["status"],
            "found": True,
            "blocked": selected["blocked"],
            "row_state": selected["row_state"],
            "actual_turns": selected["actual_turns"] if selected["actual_turns"] is not None else "",
            "input_tokens": selected["input_tokens"] if selected["input_tokens"] is not None else "",
            "cached_input_tokens": selected["cached_input_tokens"] if selected["cached_input_tokens"] is not None else "",
            "uncached_input_tokens": selected["uncached_input_tokens"] if selected["uncached_input_tokens"] is not None else "",
            "output_tokens": selected["output_tokens"] if selected["output_tokens"] is not None else "",
            "reasoning_output_tokens": selected["reasoning_output_tokens"] if selected["reasoning_output_tokens"] is not None else "",
            "billableish_tokens": selected["billableish_tokens"] if selected["billableish_tokens"] is not None else "",
            "wall_clock_seconds": selected["wall_clock_seconds"] if selected["wall_clock_seconds"] is not None else "",
            "exit_code": selected["exit_code"] if selected["exit_code"] is not None else "",
            "metrics_path": selected["metrics_path"],
            "trace_summary_path": selected["trace_summary_path"],
            "stdout_path": selected["stdout_path"],
            "stderr_path": selected["stderr_path"],
        }
        rows.append(row)
        totals["rows_found"] += 1
        if selected["blocked"]:
            totals["blocked_rows"] += 1
        elif selected["status"] == "failed":
            totals["failed_rows"] += 1
        else:
            totals["valid_completed_rows"] += 1
            for key_name in (
                "actual_turns",
                "input_tokens",
                "cached_input_tokens",
                "uncached_input_tokens",
                "output_tokens",
                "reasoning_output_tokens",
                "billableish_tokens",
            ):
                value = selected.get(key_name)
                if isinstance(value, int):
                    totals[key_name] += value
            wall_clock_seconds = selected.get("wall_clock_seconds")
            if isinstance(wall_clock_seconds, (int, float)):
                totals["wall_clock_seconds"] += float(wall_clock_seconds)

    totals["rows_missing"] = totals["scheduled_rows"] - totals["rows_found"]
    return rows, totals


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render_csv(rows: list[dict[str, Any]]) -> str:
    fieldnames = [
        "task_slug",
        "arm_slug",
        "phase",
        "expected_run_id",
        "run_id",
        "base_run_id",
        "provider",
        "runner",
        "model_label",
        "status",
        "found",
        "blocked",
        "row_state",
        "actual_turns",
        "input_tokens",
        "cached_input_tokens",
        "uncached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "billableish_tokens",
        "wall_clock_seconds",
        "exit_code",
        "metrics_path",
        "trace_summary_path",
        "stdout_path",
        "stderr_path",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({name: _csv_value(row.get(name)) for name in fieldnames})
    return buffer.getvalue()


def render_markdown(rows: list[dict[str, Any]], summary: dict[str, Any], *, repo_root: Path) -> str:
    missing_rows = [row for row in rows if row["status"] == "missing"]
    lines = [
        "# Codex Matrix Metrics",
        "",
        f"- Repo root: `{repo_root}`",
        f"- Scheduled rows: `{summary['scheduled_rows']}`",
        f"- Rows found: `{summary['rows_found']}`",
        f"- Rows missing: `{summary['rows_missing']}`",
        f"- Valid completed rows: `{summary['valid_completed_rows']}`",
        f"- Failed rows: `{summary['failed_rows']}`",
        f"- Blocked rows: `{summary['blocked_rows']}`",
        f"- Actual turns: `{summary['actual_turns']}`",
        f"- Input tokens: `{summary['input_tokens']}`",
        f"- Cached input tokens: `{summary['cached_input_tokens']}`",
        f"- Uncached input tokens: `{summary['uncached_input_tokens']}`",
        f"- Output tokens: `{summary['output_tokens']}`",
        f"- Reasoning output tokens: `{summary['reasoning_output_tokens']}`",
        f"- Billable-ish tokens: `{summary['billableish_tokens']}`",
        f"- Wall clock seconds: `{summary['wall_clock_seconds']:.3f}`",
        "",
    ]

    if missing_rows:
        lines.extend(
            [
                "## Missing Rows",
                "",
                "| task_slug | arm_slug | phase | expected_run_id |",
                "| --- | --- | --- | --- |",
            ]
        )
        for row in missing_rows:
            lines.append(
                f"| {row['task_slug']} | {row['arm_slug']} | {row['phase']} | {row['expected_run_id']} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Rows",
            "",
            "| task_slug | arm_slug | phase | status | run_id | actual_turns | input_tokens | output_tokens | wall_clock_seconds |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| {task_slug} | {arm_slug} | {phase} | {status} | {run_id} | {actual_turns} | {input_tokens} | {output_tokens} | {wall_clock_seconds} |".format(
                task_slug=row["task_slug"],
                arm_slug=row["arm_slug"],
                phase=row["phase"],
                status=row["status"],
                run_id=row["run_id"] or row["expected_run_id"],
                actual_turns=row["actual_turns"],
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
                wall_clock_seconds=row["wall_clock_seconds"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def _write_text(path: Path | str, text: str) -> None:
    if str(path) == "-":
        sys.stdout.write(text)
        if text and not text.endswith("\n"):
            sys.stdout.write("\n")
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def _resolve_output_path(repo_root: Path, path: str | None, default_path: Path) -> Path | str:
    if path is None:
        return repo_root / default_path
    if path == "-":
        return path
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def _load_provenance_model_label(run_dir: Path) -> str | None:
    provenance = _read_json(run_dir / "run_provenance.json")
    if not provenance:
        return None
    for key in ("model_label", "model", "requested_model_label"):
        value = _normalize_text(provenance.get(key))
        if value:
            return value
    return None


def _backfill_time_range(paths: list[Path]) -> tuple[int, int]:
    mtimes = []
    for path in paths:
        if not path.exists():
            continue
        try:
            mtimes.append(path.stat().st_mtime_ns)
        except OSError:
            continue
    if not mtimes:
        raise FileNotFoundError("no evidence files found to estimate wall clock time")
    return min(mtimes), max(mtimes)


def _backfill_base_run_id(run_dir: Path) -> str:
    name = run_dir.name
    if name.endswith("_full"):
        return name[: -len("_full")]
    if name.endswith("_stripped"):
        return name[: -len("_stripped")]
    return name


def backfill_run_metrics(
    *,
    run_dir: str | Path,
    task_slug: str,
    arm_slug: str,
    phase: str,
    repo_root: str | Path | None = None,
    provider: str = "codex",
    runner: str = "codex-cli",
    base_run_id: str | None = None,
    model_label: str | None = None,
    prompt_mode: str | None = None,
    output_format: str = "json",
    effort: str | None = None,
    max_turns: int | str | None = None,
    permission_mode: str | None = None,
) -> dict[str, Any]:
    repo_root_path = Path(repo_root).resolve() if repo_root is not None else Path.cwd().resolve()
    run_dir_path = Path(run_dir)
    if not run_dir_path.is_absolute():
        run_dir_path = (repo_root_path / run_dir_path).resolve()
    if not run_dir_path.is_dir():
        raise FileNotFoundError(f"run directory not found: {run_dir_path}")

    stdout_path = run_dir_path / "codex_stdout.txt"
    stderr_path = run_dir_path / "codex_stderr.txt"
    exit_path = run_dir_path / "codex_exit_code.txt"
    missing = [path.name for path in (stdout_path, stderr_path, exit_path) if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing Codex evidence files in {run_dir_path}: {', '.join(missing)}")

    resolved_model_label = _normalize_text(model_label) or _load_provenance_model_label(run_dir_path)
    if not resolved_model_label:
        raise ValueError(f"unable to determine model label for backfill in {run_dir_path}")

    try:
        exit_code = _safe_int(exit_path.read_text(encoding="utf-8", errors="replace").strip())
    except OSError as exc:  # pragma: no cover - defensive guard
        raise FileNotFoundError(f"unable to read exit code file: {exit_path}") from exc
    if exit_code is None:
        raise ValueError(f"invalid exit code in {exit_path}")

    start_ns, end_ns = _backfill_time_range([stdout_path, stderr_path, exit_path])
    label = phase.replace("_", " ")
    from benchmark_harness import runner_metrics

    data = runner_metrics.build_run_metrics(
        run_id=run_dir_path.name,
        task_slug=task_slug,
        arm_slug=arm_slug,
        label=label,
        provider=provider,
        runner=runner,
        model=resolved_model_label,
        exit_code=exit_code,
        start_ns=start_ns,
        end_ns=end_ns,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        output_format=output_format,
        effort=effort,
        max_turns=max_turns,
        permission_mode=permission_mode,
    )
    token_fields = canonical_token_fields(data)
    actual_turns = _first_positive_int(data, ("actual_turns", "num_turns", "turns"))
    wall_clock_seconds = _canonical_wall_clock_seconds(data)

    if actual_turns is None or token_fields["input_tokens"] is None or token_fields["output_tokens"] is None:
        raise ValueError(f"unable to parse token or turn evidence reliably from {run_dir_path}")

    data.update(
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_dir_path.name,
            "base_run_id": base_run_id or _backfill_base_run_id(run_dir_path),
            "phase": phase,
            "task_slug": task_slug,
            "arm_slug": arm_slug,
            "provider": provider,
            "runner": runner,
            "model_label": resolved_model_label,
            "actual_turns": actual_turns,
            "wall_clock_seconds": wall_clock_seconds
            if wall_clock_seconds is not None
            else data.get("wall_clock_seconds"),
            "exit_code": exit_code,
            "stdout_path": _relative_path(repo_root_path, stdout_path),
            "stderr_path": _relative_path(repo_root_path, stderr_path),
            "trace_summary_path": str(run_dir_path / "agent_turn_trace_summary.json"),
        }
    )
    data.update(token_fields)
    if token_fields["cached_input_tokens"] is None and token_fields["input_tokens"] is not None:
        data["uncached_input_tokens"] = token_fields["input_tokens"]

    metrics_path = run_dir_path / "run_metrics.json"
    serialized = json.dumps(data, indent=2, sort_keys=True) + "\n"
    existing = _read_json(metrics_path)
    if existing != data:
        metrics_path.write_text(serialized, encoding="utf-8")
    return data


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover Codex matrix metrics and backfill missing rows.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--task", action="append", help="Task slug to include. Repeatable.")
    parser.add_argument("--arm", action="append", help="Arm slug to include. Repeatable.")
    parser.add_argument("--phase", action="append", help="Phase to include. Repeatable.")
    parser.add_argument("--include-resume", action="store_true", help="Include full and stripped resume phases.")
    parser.add_argument("--summary-csv", help="Optional matrix summary CSV to use as the expected-row source.")
    parser.add_argument("--run-id-glob", action="append", help="Shell glob for filtering discovered run IDs. Repeatable.")
    parser.add_argument("--output-csv", help="CSV output path. Defaults inside benchmark-data.")
    parser.add_argument("--output-md", help="Markdown output path. Defaults inside benchmark-data.")

    subparsers = parser.add_subparsers(dest="command")
    backfill = subparsers.add_parser("backfill", help="Backfill one Codex run directory into canonical run_metrics.json.")
    backfill.add_argument("--run-dir", required=True)
    backfill.add_argument("--task-slug", required=True)
    backfill.add_argument("--arm-slug", required=True)
    backfill.add_argument("--phase", required=True)
    backfill.add_argument("--provider", default="codex")
    backfill.add_argument("--runner", default="codex-cli")
    backfill.add_argument("--base-run-id")
    backfill.add_argument("--model-label")
    backfill.add_argument("--prompt-mode")
    backfill.add_argument("--output-format", default="json")
    backfill.add_argument("--effort")
    backfill.add_argument("--max-turns")
    backfill.add_argument("--permission-mode")
    backfill.add_argument("--repo-root", default=".")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.command == "backfill":
        repo_root = Path(args.repo_root).resolve()
        run_dir = Path(args.run_dir)
        if not run_dir.is_absolute():
            run_dir = (repo_root / run_dir).resolve()
        try:
            backfill_run_metrics(
                run_dir=run_dir,
                repo_root=repo_root,
                task_slug=args.task_slug,
                arm_slug=args.arm_slug,
                phase=_canonical_phase(args.phase) or args.phase,
                provider=args.provider,
                runner=args.runner,
                base_run_id=args.base_run_id,
                model_label=args.model_label,
                prompt_mode=args.prompt_mode,
                output_format=args.output_format,
                effort=args.effort,
                max_turns=args.max_turns,
                permission_mode=args.permission_mode,
            )
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        return 0

    repo_root = Path(args.repo_root).resolve()
    tasks = _split_values(args.task)
    arms = _split_values(args.arm)
    phases = _split_values(args.phase)
    run_id_globs = _split_values(args.run_id_glob)
    summary_csv = Path(args.summary_csv).expanduser() if args.summary_csv else None
    if summary_csv is not None and not summary_csv.is_absolute():
        summary_csv = (repo_root / summary_csv).resolve()

    if summary_csv is None:
        if not tasks or not arms:
            print("ERROR: either --summary-csv or both --task and --arm must be supplied.", file=sys.stderr)
            return 2
    if not phases:
        phases = [PHASE_INITIAL]
        if args.include_resume:
            phases.extend([PHASE_FULL_RESUME, PHASE_STRIPPED_RESUME])
    phases = [phase for phase in (_canonical_phase(phase) for phase in phases) if phase]

    rows, summary = summarize_matrix(
        repo_root=repo_root,
        tasks=tasks,
        arms=arms,
        phases=phases,
        summary_csv=summary_csv,
        run_id_globs=run_id_globs,
    )

    output_csv = _resolve_output_path(repo_root, args.output_csv, DEFAULT_OUTPUT_CSV)
    output_md = _resolve_output_path(repo_root, args.output_md, DEFAULT_OUTPUT_MD)

    csv_text = render_csv(rows)
    markdown_text = render_markdown(rows, summary, repo_root=repo_root)
    _write_text(output_csv, csv_text)
    _write_text(output_md, markdown_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
