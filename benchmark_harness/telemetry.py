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
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


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
    except OSError:
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


def collect_run(*, root: str | Path, run_id: str, out: str | Path | None = None) -> Path:
    root_path = Path(root).resolve()
    telemetry_path = Path(out) if out else root_path / "benchmark-data" / "runs" / run_id / "telemetry.jsonl"
    phases = (
        ("initial", root_path / "benchmark-data" / "runs" / run_id, root_path / "benchmark-data" / "workspaces" / run_id / "repo"),
        ("full_resume", root_path / "benchmark-data" / "resume-runs" / f"{run_id}_full", root_path / "benchmark-data" / "resume-workspaces" / run_id / "full" / "repo"),
        ("stripped_resume", root_path / "benchmark-data" / "resume-runs" / f"{run_id}_stripped", root_path / "benchmark-data" / "resume-workspaces" / run_id / "stripped" / "repo"),
    )

    emit(telemetry_path, "telemetry.collect_start", run_id=run_id, fields={"root": root_path.as_posix()})

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

    emit(telemetry_path, "telemetry.collect_end", run_id=run_id, fields={"path": telemetry_path.as_posix()})
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
