from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmark_harness.solution_latency import summarize_solution_latency

FINAL_ONLY_NOTE = "final_only_no_per_turn_trace"


def _read_text(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _read_json(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    if text is None:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _metrics_value(run_dir: Path, key: str) -> Any:
    metrics = _read_json(run_dir / "run_metrics.json")
    return metrics.get(key)


def _infer_exit_from_files(run_dir: Path, filenames: list[str], kind: str) -> int | None:
    from benchmark_harness.scorecard import _infer_command_exit

    paths = [run_dir / filename for filename in filenames]
    return _infer_command_exit(paths, kind)


def _phase_exits(run_dir: Path, *, phase: str) -> tuple[int | None, int | None]:
    if phase == "initial":
        return (
            _infer_exit_from_files(run_dir, ["verification_final.txt"], "verify"),
            _infer_exit_from_files(run_dir, ["hidden_evaluator_final.txt"], "hidden"),
        )
    return (
        _infer_exit_from_files(run_dir, ["verification.txt"], "verify"),
        _infer_exit_from_files(run_dir, ["hidden_evaluator.txt"], "hidden"),
    )


def build_summary(run_dir: Path, *, phase: str, verify_exit: int, hidden_exit: int) -> dict[str, Any]:
    metrics = _read_json(run_dir / "run_metrics.json")
    inferred = summarize_solution_latency(run_dir, verify_exit=verify_exit, hidden_exit=hidden_exit)
    observable = bool(inferred.get("solution_latency_observable"))

    return {
        "schema_version": 1,
        "phase": phase,
        "actual_turns": inferred.get("actual_turns"),
        "max_turns": _as_int(metrics.get("max_turns")),
        "terminal_reason": metrics.get("terminal_reason"),
        "claude_exit_code": _as_int(metrics.get("claude_exit_code")),
        "final_verify_exit": verify_exit,
        "final_hidden_exit": hidden_exit,
        "final_green": verify_exit == 0 and hidden_exit == 0,
        "first_green_turn": inferred.get("first_green_turn"),
        "turns_after_first_green": inferred.get("turns_after_first_green"),
        "permission_denials_after_first_green": inferred.get("permission_denials_after_first_green"),
        "solution_latency_observable": observable,
        "source": inferred.get("solution_latency_source") if observable else "final_collect_only",
        "note": inferred.get("solution_latency_note") if observable else FINAL_ONLY_NOTE,
    }


def write_summary(run_dir: Path, *, phase: str, verify_exit: int, hidden_exit: int) -> Path:
    path = run_dir / "solution_latency.json"
    summary = build_summary(run_dir, phase=phase, verify_exit=verify_exit, hidden_exit=hidden_exit)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def annotate_run(root: Path, run_id: str) -> list[Path]:
    phase_dirs = [
        ("initial", root / "benchmark-data" / "runs" / run_id),
        ("full_resume", root / "benchmark-data" / "resume-runs" / f"{run_id}_full"),
        ("stripped_resume", root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped"),
    ]

    written: list[Path] = []
    for phase, run_dir in phase_dirs:
        if not run_dir.exists():
            continue
        verify_exit, hidden_exit = _phase_exits(run_dir, phase=phase)
        if verify_exit is None or hidden_exit is None:
            continue
        written.append(write_summary(run_dir, phase=phase, verify_exit=verify_exit, hidden_exit=hidden_exit))
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit solution_latency.json for collected benchmark phases.")
    subparsers = parser.add_subparsers(dest="command")

    one = subparsers.add_parser("one", help="Emit one phase summary")
    one.add_argument("--run-dir", required=True, type=Path)
    one.add_argument("--phase", required=True)
    one.add_argument("--verify-exit", required=True, type=int)
    one.add_argument("--hidden-exit", required=True, type=int)

    annotate = subparsers.add_parser("annotate", help="Emit summaries for all collected phases in one run")
    annotate.add_argument("--root", required=True, type=Path)
    annotate.add_argument("--run-id", required=True)

    args = parser.parse_args(argv)

    if args.command == "one":
        print(write_summary(args.run_dir, phase=args.phase, verify_exit=args.verify_exit, hidden_exit=args.hidden_exit))
        return 0
    if args.command == "annotate":
        for path in annotate_run(args.root, args.run_id):
            print(path)
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
