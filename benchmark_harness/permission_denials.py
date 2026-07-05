from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

PERMISSION_DENIAL_METRIC_KEYS = (
    "permission_denials_count",
    "permission_denied_tools",
    "permission_denied_bash_count",
)
TOOL_NAME_KEYS = ("tool_name", "tool", "name", "server_tool_name")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _tool_name(denial: Any) -> str | None:
    if isinstance(denial, str) and denial.strip():
        return denial.strip()
    if not isinstance(denial, Mapping):
        return None
    for key in TOOL_NAME_KEYS:
        value = denial.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def extract_permission_denial_metrics(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Extract metadata-only permission-denial counts from Claude JSON output."""
    denials = raw.get("permission_denials")
    if not isinstance(denials, list):
        denials = []

    tools = [_tool_name(denial) for denial in denials]
    tool_counts = Counter(tool for tool in tools if tool)
    denied_tools = sorted(tool_counts)

    return {
        "permission_denials_count": len(denials),
        "permission_denied_tools": denied_tools,
        "permission_denied_bash_count": tool_counts.get("Bash", 0),
    }


def extract_from_stdout(stdout_text: str) -> dict[str, Any]:
    try:
        raw = json.loads(stdout_text)
    except json.JSONDecodeError:
        raw = None
    if not isinstance(raw, dict):
        raw = None

    if raw is not None:
        return extract_permission_denial_metrics(raw)

    last_result: dict[str, Any] | None = None
    for line in stdout_text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            if isinstance(event.get("permission_denials"), list):
                last_result = event
            elif str(event.get("type", "")).lower() == "result" and last_result is None:
                last_result = event

    if last_result is None:
        return {}
    return extract_permission_denial_metrics(last_result)


def annotate_metrics_file(metrics_path: str | Path) -> bool:
    metrics_file = Path(metrics_path)
    stdout_file = metrics_file.with_name("claude_stdout.txt")
    if not metrics_file.is_file() or not stdout_file.is_file():
        return False

    metrics = _read_json(metrics_file)
    if not metrics:
        return False

    fields = extract_from_stdout(stdout_file.read_text(encoding="utf-8", errors="replace"))
    if not fields:
        return False

    metrics.update(fields)
    metrics_file.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True


def discover_metrics_files(root: str | Path) -> list[Path]:
    root_path = Path(root)
    candidates = [
        root_path / "benchmark-data" / "runs",
        root_path / "benchmark-data" / "resume-runs",
    ]
    paths: list[Path] = []
    for candidate in candidates:
        if candidate.is_dir():
            paths.extend(sorted(candidate.glob("*/run_metrics.json")))
    return paths


def annotate_discovered(root: str | Path = ".") -> int:
    return sum(1 for path in discover_metrics_files(root) if annotate_metrics_file(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Annotate run_metrics.json with Claude permission-denial counts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    annotate = subparsers.add_parser("annotate", help="Annotate one or more run_metrics.json files.")
    annotate.add_argument("metrics", nargs="*", help="Specific run_metrics.json files to annotate.")
    annotate.add_argument("--root", default=".", help="Repository root to scan when no metrics files are supplied.")

    args = parser.parse_args(argv)
    if args.command == "annotate":
        if args.metrics:
            updated = sum(1 for raw in args.metrics if annotate_metrics_file(raw))
        else:
            updated = annotate_discovered(args.root)
        print(f"permission_denial_metrics_updated={updated}")
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
