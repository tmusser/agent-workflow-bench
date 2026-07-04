from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1
TRUTHY = {"1", "true", "yes", "on"}
SENSITIVE_KEY_PARTS = (
    "body",
    "completion",
    "content",
    "message",
    "prompt",
    "response",
    "secret",
    "stderr",
    "stdout",
    "text",
)
SAFE_SUFFIXES = ("_bytes", "_lines", "_path", "_sha256", "_tokens")
MAX_STRING_LENGTH = 300
DEFAULT_CONTEXT_WINDOW_TOKENS = 200_000
CONTEXT_WINDOW_ENV_KEYS = ("TELEMETRY_CONTEXT_WINDOW_TOKENS", "CONTEXT_WINDOW_TOKENS")

LLM_METRIC_KEYS = (
    "label",
    "model",
    "effort",
    "max_turns",
    "permission_mode",
    "output_format",
    "claude_exit_code",
    "reached_max_turns",
    "wall_clock_seconds",
    "stdout_bytes",
    "stderr_bytes",
    "stdout_lines",
    "stderr_lines",
    "actual_turns",
    "duration_ms",
    "duration_api_ms",
    "total_cost_usd",
    "terminal_reason",
    "stop_reason",
    "usage_input_tokens",
    "usage_output_tokens",
    "usage_cache_creation_input_tokens",
    "usage_cache_read_input_tokens",
)
PROVENANCE_KEYS = (
    "requested_arm_slug",
    "resolved_arm_slug",
    "arm_slug_mismatch",
    "alias_applied",
    "alias_reason",
    "context_mode",
    "arm_wrapper_path",
    "arm_wrapper_sha256",
    "task_prompt_path",
    "task_prompt_sha256",
    "resume_prompt_path",
    "resume_prompt_sha256",
)
KNOWN_ARTIFACTS = (
    "SPEC.md",
    "PLAN.md",
    "TODO.md",
    "VERIFY.md",
    "HANDOFF.md",
    "BUGS.md",
    "SKILL_RUNTIME_PROOF.md",
    "BUGFIX_NOTES.md",
    "BUGFIX_REVIEW.md",
    "FRESH_SESSION_REVIEW.md",
    "IMPLEMENTATION_NOTE.md",
    "IMPLEMENTATION_NOTES.md",
    "MIGRATION_NOTES.md",
    "DATA_AUDIT.md",
    "TRUST_AUDIT.md",
)


def is_enabled(env: Mapping[str, str] | None = None) -> bool:
    values = os.environ if env is None else env
    return values.get("ENABLE_TELEMETRY", "").strip().lower() in TRUTHY


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    if normalized.endswith(SAFE_SUFFIXES):
        return False
    tokens = set(normalized.split("_"))
    return normalized in SENSITIVE_KEY_PARTS or any(part in tokens for part in SENSITIVE_KEY_PARTS)


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Path):
        value = value.as_posix()
    if isinstance(value, str):
        return value if len(value) <= MAX_STRING_LENGTH else value[:MAX_STRING_LENGTH] + "...[truncated]"
    return str(value)


def sanitize_fields(fields: Mapping[str, Any] | None) -> dict[str, Any]:
    if not fields:
        return {}
    clean: dict[str, Any] = {}
    for key, value in fields.items():
        if _sensitive_key(key):
            raise ValueError(f"telemetry field name is too content-like: {key}")
        if isinstance(value, Mapping):
            clean[key] = sanitize_fields(value)
        elif isinstance(value, (list, tuple)):
            clean[key] = [
                sanitize_fields(item) if isinstance(item, Mapping) else _safe_scalar(item)
                for item in value
            ]
        else:
            clean[key] = _safe_scalar(value)
    return clean


def build_event(
    event_type: str,
    *,
    run_id: str | None = None,
    task_slug: str | None = None,
    arm_slug: str | None = None,
    phase: str | None = None,
    label: str | None = None,
    fields: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not event_type.strip():
        raise ValueError("event_type is required")
    event: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": utc_now(),
        "event_type": event_type.strip(),
    }
    for key, value in (
        ("run_id", run_id),
        ("task_slug", task_slug),
        ("arm_slug", arm_slug),
        ("phase", phase),
        ("label", label),
    ):
        if value is not None:
            event[key] = value
    clean_fields = sanitize_fields(fields)
    if clean_fields:
        event["fields"] = clean_fields
    return event


def write_event(path: str | Path, event: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(event), sort_keys=True, separators=(",", ":")) + "\n")


def emit(path: str | Path, event_type: str, **kwargs: Any) -> dict[str, Any]:
    event = build_event(event_type, **kwargs)
    write_event(path, event)
    return event


def read_events(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _whitelist(data: Mapping[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    return {key: data[key] for key in keys if key in data and data[key] is not None}


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _file_metadata(path: Path, root: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    stat = path.stat()
    return {"path": _rel(path, root), "bytes": stat.st_size}


def _collect_files(root: Path, paths: Iterable[Path]) -> list[dict[str, Any]]:
    files = [metadata for path in paths if (metadata := _file_metadata(path, root))]
    return sorted(files, key=lambda item: str(item["path"]))


def _positive_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(str(value).replace("_", "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def context_window_config(env: Mapping[str, str] | None = None) -> tuple[int, str]:
    values = os.environ if env is None else env
    for key in CONTEXT_WINDOW_ENV_KEYS:
        parsed = _positive_int(values.get(key))
        if parsed is not None:
            return parsed, key
    return DEFAULT_CONTEXT_WINDOW_TOKENS, "default"


def estimate_tokens_from_chars(char_count: int) -> int:
    if char_count <= 0:
        return 0
    return max(1, (char_count + 3) // 4)


def context_pressure_status(used_pct: float) -> str:
    if used_pct >= 90:
        return "critical"
    if used_pct >= 75:
        return "high"
    if used_pct >= 50:
        return "medium"
    return "low"


def _path_from_provenance(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate


def _input_file_for_phase(phase: str, out_dir: Path, provenance: Mapping[str, Any], root: Path) -> Path | None:
    candidates: list[Path] = []
    if phase == "initial":
        candidates.append(out_dir / "prompt.md")
        task_prompt = _path_from_provenance(root, provenance.get("task_prompt_path"))
        if task_prompt is not None:
            candidates.append(task_prompt)
    else:
        resume_prompt = _path_from_provenance(root, provenance.get("resume_prompt_path"))
        if resume_prompt is not None:
            candidates.append(resume_prompt)

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _context_window_fields(
    *,
    phase: str,
    out_dir: Path,
    root: Path,
    metrics: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    window_tokens, window_source = context_window_config()
    fields: dict[str, Any] = {
        "context_window_tokens": window_tokens,
        "context_window_source": window_source,
    }

    used_tokens = _positive_int(metrics.get("usage_input_tokens"))
    if used_tokens is not None:
        fields["estimator"] = "provider_usage_input_tokens"
        fields["usage_input_tokens"] = used_tokens
    else:
        input_file = _input_file_for_phase(phase, out_dir, provenance, root)
        if input_file is None:
            fields["estimator"] = "unavailable"
            fields["status"] = "unknown"
            fields["reason"] = "no_usage_tokens_or_input_file"
            return fields
        try:
            data = input_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            fields["estimator"] = "unavailable"
            fields["status"] = "unknown"
            fields["reason"] = "input_file_unreadable"
            return fields

        used_tokens = estimate_tokens_from_chars(len(data))
        stat = input_file.stat()
        fields.update(
            {
                "estimator": "local_chars_div_4",
                "estimated_input_tokens": used_tokens,
                "input_file_path": _rel(input_file, root),
                "input_file_bytes": stat.st_size,
                "input_file_chars": len(data),
            }
        )

    used_pct = round((used_tokens / window_tokens) * 100, 2)
    fields["context_window_used_pct"] = used_pct
    fields["remaining_context_window_tokens"] = max(window_tokens - used_tokens, 0)
    fields["status"] = context_pressure_status(used_pct)
    fields["is_estimate"] = fields["estimator"] != "provider_usage_input_tokens"
    return fields


def collect_run(*, root: str | Path, run_id: str, out: str | Path | None = None) -> Path:
    root_path = Path(root).resolve()
    telemetry_path = Path(out) if out else root_path / "benchmark-data" / "runs" / run_id / "telemetry.jsonl"
    phases = (
        ("initial", root_path / "benchmark-data" / "runs" / run_id, root_path / "benchmark-data" / "workspaces" / run_id / "repo"),
        ("full_resume", root_path / "benchmark-data" / "resume-runs" / f"{run_id}_full", root_path / "benchmark-data" / "resume-workspaces" / run_id / "full" / "repo"),
        ("stripped_resume", root_path / "benchmark-data" / "resume-runs" / f"{run_id}_stripped", root_path / "benchmark-data" / "resume-workspaces" / run_id / "stripped" / "repo"),
    )

    emit(telemetry_path, "telemetry.collect_start", run_id=run_id)

    for phase, out_dir, repo_dir in phases:
        metrics = _read_json(out_dir / "run_metrics.json")
        if metrics:
            emit(
                telemetry_path,
                "llm_call.summary",
                run_id=str(metrics.get("run_id") or run_id),
                task_slug=str(metrics["task_slug"]) if metrics.get("task_slug") else None,
                arm_slug=str(metrics["arm_slug"]) if metrics.get("arm_slug") else None,
                phase=phase,
                label=str(metrics.get("label") or phase),
                fields=_whitelist(metrics, LLM_METRIC_KEYS),
            )

        provenance = _read_json(out_dir / "run_provenance.json")
        if provenance:
            arm = provenance.get("resolved_arm_slug") or provenance.get("requested_arm_slug")
            emit(
                telemetry_path,
                "harness.provenance",
                run_id=run_id,
                task_slug=str(provenance["task_slug"]) if provenance.get("task_slug") else None,
                arm_slug=str(arm) if arm else None,
                phase=phase,
                fields=_whitelist(provenance, PROVENANCE_KEYS),
            )

        if metrics or provenance:
            arm = metrics.get("arm_slug") or provenance.get("resolved_arm_slug") or provenance.get("requested_arm_slug")
            task = metrics.get("task_slug") or provenance.get("task_slug")
            label = metrics.get("label") or phase
            emit(
                telemetry_path,
                "context_window.status",
                run_id=str(metrics.get("run_id") or run_id),
                task_slug=str(task) if task else None,
                arm_slug=str(arm) if arm else None,
                phase=phase,
                label=str(label),
                fields=_context_window_fields(
                    phase=phase,
                    out_dir=out_dir,
                    root=root_path,
                    metrics=metrics,
                    provenance=provenance,
                ),
            )

        outputs = _collect_files(
            root_path,
            [
                out_dir / "verification_final.txt",
                out_dir / "hidden_evaluator_final.txt",
                out_dir / "verification.txt",
                out_dir / "hidden_evaluator.txt",
                out_dir / "diff.patch",
                out_dir / "diff_stat.txt",
                out_dir / "git_status_final.txt",
                out_dir / "git_status.txt",
                out_dir / "INITIAL_NOT_READY.txt",
                out_dir / "task7_hidden_evaluator.json",
            ],
        )
        if outputs:
            emit(telemetry_path, "harness.outputs", run_id=run_id, phase=phase, fields={"files": outputs})

        artifacts = _collect_files(root_path, [repo_dir / name for name in KNOWN_ARTIFACTS])
        if artifacts:
            emit(telemetry_path, "workflow.artifacts", run_id=run_id, phase=phase, fields={"files": artifacts})

    emit(telemetry_path, "telemetry.collect_end", run_id=run_id, fields={"path": _rel(telemetry_path, root_path)})
    return telemetry_path


def _parse_field(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("fields must use key=value")
    key, value = raw.split("=", 1)
    if not key:
        raise argparse.ArgumentTypeError("field key cannot be empty")
    return key, value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local-only JSONL telemetry helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    emit_parser = subparsers.add_parser("emit", help="Append one metadata-only telemetry event.")
    emit_parser.add_argument("--path", required=True)
    emit_parser.add_argument("--event-type", required=True)
    emit_parser.add_argument("--run-id")
    emit_parser.add_argument("--task-slug")
    emit_parser.add_argument("--arm-slug")
    emit_parser.add_argument("--phase")
    emit_parser.add_argument("--label")
    emit_parser.add_argument("--field", action="append", type=_parse_field, default=[])

    collect_parser = subparsers.add_parser("collect-run", help="Build telemetry.jsonl from existing run artifacts.")
    collect_parser.add_argument("--root", default=".")
    collect_parser.add_argument("--run-id", required=True)
    collect_parser.add_argument("--out")

    args = parser.parse_args(argv)
    if args.command == "emit":
        emit(
            args.path,
            args.event_type,
            run_id=args.run_id,
            task_slug=args.task_slug,
            arm_slug=args.arm_slug,
            phase=args.phase,
            label=args.label,
            fields=dict(args.field or []),
        )
        return 0
    if args.command == "collect-run":
        collect_run(root=args.root, run_id=args.run_id, out=args.out)
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
