from __future__ import annotations

import argparse
import csv
import json
import io
import re
import sys
from pathlib import Path
from typing import Iterable


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _parse_scalar(value: str) -> object:
    text = value.strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    if re.fullmatch(r"-?\d+", text):
        try:
            return int(text)
        except ValueError:
            return text
    if re.fullmatch(r"-?\d+\.\d+", text):
        try:
            return float(text)
        except ValueError:
            return text
    return text


def _load_txt_metrics(path: Path) -> dict[str, object]:
    data: dict[str, object] = {}
    for raw_line in _read_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, value = line.split(":", 1)
        elif "=" in line:
            key, value = line.split("=", 1)
        else:
            continue
        data[key.strip()] = _parse_scalar(value)
    return data


def load_run_metrics(path: Path) -> dict[str, object]:
    if path.suffix == ".json":
        try:
            data = json.loads(_read_text(path))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return _load_txt_metrics(path)


def discover_run_metrics(paths: Iterable[Path]) -> list[Path]:
    chosen: dict[str, Path] = {}
    for root in paths:
        root = Path(root)
        if not root.exists():
            continue
        if root.is_file():
            if root.name in {"run_metrics.json", "run_metrics.txt"}:
                chosen[str(root.parent)] = root
            continue
        for path in sorted(root.rglob("run_metrics.json")):
            chosen[str(path.parent)] = path
        for path in sorted(root.rglob("run_metrics.txt")):
            chosen.setdefault(str(path.parent), path)
    return [chosen[key] for key in sorted(chosen)]


def _extract_exit_from_text(text: str, kind: str) -> int | None:
    lowered = text.lower()
    if kind == "verify":
        explicit_patterns = [
            r"\bverify(?:ication)?(?:_|-|\s)*exit(?:_|-|\s)*(?:code)?\s*[:=]\s*(-?\d+)\b",
            r"\bverification_exit\s*[:=]\s*(-?\d+)\b",
            r"\bverify_exit\s*[:=]\s*(-?\d+)\b",
        ]
        fail_markers = [
            "traceback (most recent call last)",
            "assertionerror",
            "failed",
            "error",
            "exception",
        ]
        success_markers = [
            "passed in",
            "verification passed",
            "verify.sh passed",
            "all tests passed",
            "no impossible churn detected",
        ]
    else:
        explicit_patterns = [
            r"\bhidden(?:_|-|\s)*evaluator(?:_|-|\s)*exit(?:_|-|\s)*(?:code)?\s*[:=]\s*(-?\d+)\b",
            r"\bhidden_evaluator_exit\s*[:=]\s*(-?\d+)\b",
        ]
        fail_markers = [
            "traceback (most recent call last)",
            "assertionerror",
            "hidden contract failed",
            "failed",
            "error",
            "exception",
        ]
        success_markers = [
            "hidden evaluator passed",
            "passed",
        ]

    for pattern in explicit_patterns:
        match = re.search(pattern, lowered)
        if match:
            return int(match.group(1))

    if any(marker in lowered for marker in fail_markers):
        return 1
    if any(marker in lowered for marker in success_markers):
        return 0
    return None


def _sibling_exit_code(run_dir: Path, kind: str) -> int | None:
    candidate_names = (
        ("verification_final.txt", "verification.txt")
        if kind == "verify"
        else ("hidden_evaluator_final.txt", "hidden_evaluator.txt")
    )
    for name in candidate_names:
        path = run_dir / name
        if not path.exists():
            continue
        exit_code = _extract_exit_from_text(_read_text(path), kind)
        if exit_code is not None:
            return exit_code
    return None


def _diff_bytes(run_dir: Path) -> int | None:
    diff_path = run_dir / "diff.patch"
    if not diff_path.exists():
        return None
    try:
        return diff_path.stat().st_size
    except OSError:
        return None


def summarize_run_effort(paths: Iterable[Path]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for metrics_path in discover_run_metrics(paths):
        run_dir = metrics_path.parent
        metrics = load_run_metrics(metrics_path)
        if not metrics:
            continue

        row: dict[str, object] = {
            "run_id": metrics.get("run_id") or run_dir.name,
            "label": metrics.get("label", ""),
            "arm_slug": metrics.get("arm_slug", ""),
            "model": metrics.get("model", ""),
            "max_turns": metrics.get("max_turns", ""),
            "exit_code": metrics.get("claude_exit_code", metrics.get("exit_code", "")),
            "reached_max_turns": metrics.get("reached_max_turns", "unknown"),
            "wall_clock_seconds": metrics.get("wall_clock_seconds", ""),
            "stdout_lines": metrics.get("stdout_lines", ""),
            "stderr_lines": metrics.get("stderr_lines", ""),
            "diff_bytes": _diff_bytes(run_dir),
            "verification_exit": _sibling_exit_code(run_dir, "verify"),
            "hidden_evaluator_exit": _sibling_exit_code(run_dir, "hidden"),
        }
        rows.append(row)
    rows.sort(key=lambda row: (str(row.get("run_id", "")), str(row.get("label", "")), str(row.get("arm_slug", ""))))
    return rows


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render_csv(rows: list[dict[str, object]]) -> str:
    fieldnames = [
        "run_id",
        "label",
        "arm_slug",
        "model",
        "max_turns",
        "exit_code",
        "reached_max_turns",
        "wall_clock_seconds",
        "stdout_lines",
        "stderr_lines",
        "diff_bytes",
        "verification_exit",
        "hidden_evaluator_exit",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({name: _csv_value(row.get(name)) for name in fieldnames})
    return buffer.getvalue()


def render_markdown(rows: list[dict[str, object]]) -> str:
    headers = [
        "run_id",
        "label",
        "arm_slug",
        "model",
        "max_turns",
        "exit_code",
        "reached_max_turns",
        "wall_clock_seconds",
        "stdout_lines",
        "stderr_lines",
        "diff_bytes",
        "verification_exit",
        "hidden_evaluator_exit",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_csv_value(row.get(name)) for name in headers) + " |")
    return "\n".join(lines) + ("\n" if lines else "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize Claude run effort across benchmark run directories.")
    parser.add_argument("paths", nargs="+", help="Run roots to scan for run_metrics.json or run_metrics.txt")
    parser.add_argument(
        "--format",
        choices=("csv", "markdown"),
        default="csv",
        help="Output format for the summary table.",
    )
    args = parser.parse_args(argv)

    rows = summarize_run_effort(Path(path) for path in args.paths)
    if not rows:
        parser.error("no run_metrics files found")

    if args.format == "markdown":
        sys.stdout.write(render_markdown(rows))
    else:
        sys.stdout.write(render_csv(rows))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
