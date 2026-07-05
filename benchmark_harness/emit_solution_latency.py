from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmark_harness.solution_latency import summarize_solution_latency

FINAL_ONLY_NOTE = "final_only_no_per_turn_trace"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit solution_latency.json for one collected benchmark phase.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--verify-exit", required=True, type=int)
    parser.add_argument("--hidden-exit", required=True, type=int)
    args = parser.parse_args(argv)

    print(write_summary(args.run_dir, phase=args.phase, verify_exit=args.verify_exit, hidden_exit=args.hidden_exit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
