from __future__ import annotations

import argparse
import json
import pathlib
import re
from typing import Any, Mapping

TOKEN_KEYS = (
    "usage_input_tokens",
    "usage_output_tokens",
    "usage_cache_creation_input_tokens",
    "usage_cache_read_input_tokens",
    "input_tokens",
    "output_tokens",
    "prompt_tokens",
    "completion_tokens",
    "total_input_tokens",
    "total_output_tokens",
    "total_tokens",
    "cached_input_tokens",
    "reasoning_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
)
USAGE_TOKEN_KEYS = (
    "input_tokens",
    "output_tokens",
    "prompt_tokens",
    "completion_tokens",
    "total_input_tokens",
    "total_output_tokens",
    "total_tokens",
    "cached_input_tokens",
    "reasoning_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
)
SAFE_JSON_KEYS = (
    "actual_turns",
    "num_turns",
    "duration_ms",
    "duration_api_ms",
    "total_cost_usd",
    "terminal_reason",
    "stop_reason",
)


def _read_text(path: str | pathlib.Path) -> str:
    try:
        return pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _file_size(path: pathlib.Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _line_count(path: pathlib.Path) -> int:
    text = _read_text(path)
    return len(text.splitlines()) if text else 0


def _safe_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).replace("_", "").strip())
    except (TypeError, ValueError):
        return None


def _provider_exit_key(provider: str) -> str | None:
    normalized = provider.strip().lower().replace("-", "_")
    if not normalized or not re.fullmatch(r"[a-z0-9_]+", normalized):
        return None
    return f"{normalized}_exit_code"


def _copy_safe_json_fields(data: dict[str, object], raw: Mapping[str, Any]) -> None:
    for key in SAFE_JSON_KEYS:
        if raw.get(key) is not None:
            target_key = "actual_turns" if key == "num_turns" else key
            data[target_key] = raw[key]
    for key in TOKEN_KEYS:
        if raw.get(key) is not None:
            data[key] = raw[key]

    usage = raw.get("usage")
    if isinstance(usage, Mapping):
        for key in USAGE_TOKEN_KEYS:
            if usage.get(key) is not None:
                if key == "cache_creation_input_tokens":
                    data["usage_cache_creation_input_tokens"] = usage[key]
                elif key == "cache_read_input_tokens":
                    data["usage_cache_read_input_tokens"] = usage[key]
                else:
                    data[key] = usage[key]

    codex_usage = raw.get("codex_usage")
    if isinstance(codex_usage, Mapping):
        for key in USAGE_TOKEN_KEYS:
            if codex_usage.get(key) is not None:
                data[key] = codex_usage[key]


def _parse_json_stdout(data: dict[str, object], stdout_text: str) -> None:
    if not stdout_text.strip():
        return
    try:
        raw = json.loads(stdout_text)
    except json.JSONDecodeError:
        return
    if isinstance(raw, Mapping):
        _copy_safe_json_fields(data, raw)


def _max_turns_status(stdout_text: str, stderr_text: str, data: Mapping[str, object]) -> bool | str:
    stop_reason = str(data.get("stop_reason") or "").strip().lower()
    terminal_reason = str(data.get("terminal_reason") or "").strip().lower()
    if stop_reason == "max_turns" or terminal_reason == "max_turns":
        return True
    if stop_reason or terminal_reason:
        return False
    combined = f"{stdout_text}\n{stderr_text}".lower()
    if "reached max turns" in combined or re.search(r"\bmax turns\b", combined):
        return True
    return False if stdout_text or stderr_text else "unknown"


def build_run_metrics(
    *,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    label: str,
    provider: str,
    runner: str,
    model: str,
    exit_code: int,
    start_ns: int,
    end_ns: int,
    stdout_path: str | pathlib.Path,
    stderr_path: str | pathlib.Path,
    output_format: str = "text",
    effort: str | None = None,
    max_turns: int | str | None = None,
    permission_mode: str | None = None,
) -> dict[str, object]:
    stdout_file = pathlib.Path(stdout_path)
    stderr_file = pathlib.Path(stderr_path)
    stdout_text = _read_text(stdout_file)
    stderr_text = _read_text(stderr_file)
    wall_clock_seconds = (int(end_ns) - int(start_ns)) / 1_000_000_000

    data: dict[str, object] = {
        "run_id": run_id,
        "task_slug": task_slug,
        "arm_slug": arm_slug,
        "label": label,
        "provider": provider,
        "runner": runner,
        "model": model,
        "output_format": output_format,
        "runner_exit_code": int(exit_code),
        "agent_exit_code": int(exit_code),
        "wall_clock_seconds": round(wall_clock_seconds, 3),
        "stdout_bytes": _file_size(stdout_file),
        "stderr_bytes": _file_size(stderr_file),
        "stdout_lines": _line_count(stdout_file),
        "stderr_lines": _line_count(stderr_file),
    }
    provider_exit_key = _provider_exit_key(provider)
    if provider_exit_key:
        data[provider_exit_key] = int(exit_code)
    if effort:
        data["effort"] = effort
    parsed_max_turns = _safe_int(max_turns)
    if parsed_max_turns is not None:
        data["max_turns"] = parsed_max_turns
    if permission_mode:
        data["permission_mode"] = permission_mode

    if output_format.strip().lower() == "json":
        _parse_json_stdout(data, stdout_text)

    data["reached_max_turns"] = _max_turns_status(stdout_text, stderr_text, data)
    return data


def write_run_metrics(path: str | pathlib.Path, **kwargs: Any) -> dict[str, object]:
    data = build_run_metrics(**kwargs)
    out = pathlib.Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write provider-neutral runner metadata for benchmark runs.")
    parser.add_argument("command", choices=["write"])
    parser.add_argument("--out", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-slug", required=True)
    parser.add_argument("--arm-slug", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--exit-code", required=True, type=int)
    parser.add_argument("--start-ns", required=True, type=int)
    parser.add_argument("--end-ns", required=True, type=int)
    parser.add_argument("--stdout", required=True)
    parser.add_argument("--stderr", required=True)
    parser.add_argument("--output-format", default="text")
    parser.add_argument("--effort")
    parser.add_argument("--max-turns")
    parser.add_argument("--permission-mode")
    args = parser.parse_args(argv)

    write_run_metrics(
        args.out,
        run_id=args.run_id,
        task_slug=args.task_slug,
        arm_slug=args.arm_slug,
        label=args.label,
        provider=args.provider,
        runner=args.runner,
        model=args.model,
        exit_code=args.exit_code,
        start_ns=args.start_ns,
        end_ns=args.end_ns,
        stdout_path=args.stdout,
        stderr_path=args.stderr,
        output_format=args.output_format,
        effort=args.effort,
        max_turns=args.max_turns,
        permission_mode=args.permission_mode,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
