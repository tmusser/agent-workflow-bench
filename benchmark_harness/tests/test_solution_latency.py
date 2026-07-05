from __future__ import annotations

import json
from pathlib import Path

from benchmark_harness.solution_latency import summarize_solution_latency


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_solution_latency_reports_not_observable_without_turn_trace(tmp_path: Path):
    run_dir = tmp_path / "run"
    write(run_dir / "run_metrics.json", json.dumps({"actual_turns": 21}) + "\n")

    result = summarize_solution_latency(run_dir, verify_exit=0, hidden_exit=0)

    assert result["solution_latency_observable"] is False
    assert result["actual_turns"] == 21
    assert result["first_green_turn"] is None
    assert result["turns_after_first_green"] is None
    assert result["solution_latency_note"] == "not_observable"


def test_solution_latency_reads_explicit_summary(tmp_path: Path):
    run_dir = tmp_path / "run"
    write(run_dir / "run_metrics.json", json.dumps({"actual_turns": 21}) + "\n")
    write(
        run_dir / "solution_latency.json",
        json.dumps(
            {
                "first_green_turn": 7,
                "permission_denials_after_first_green": 3,
                "note": "computed_by_harness",
            }
        )
        + "\n",
    )

    result = summarize_solution_latency(run_dir, verify_exit=0, hidden_exit=0)

    assert result["solution_latency_observable"] is True
    assert result["actual_turns"] == 21
    assert result["first_green_turn"] == 7
    assert result["turns_after_first_green"] == 14
    assert result["permission_denials_after_first_green"] == 3
    assert result["solution_latency_source"] == "solution_latency.json"
    assert result["solution_latency_note"] == "computed_by_harness"


def test_solution_latency_reads_jsonl_turn_events(tmp_path: Path):
    run_dir = tmp_path / "run"
    write(run_dir / "run_metrics.json", json.dumps({"actual_turns": 10}) + "\n")
    events = [
        {"turn": 1, "verify_exit": 1, "hidden_evaluator_exit": 1},
        {"turn": 4, "verify_exit": 0, "hidden_evaluator_exit": 0},
        {"turn": 5, "permission_denied": True},
        {"turn": 8, "event": "permission_denied"},
    ]
    write(run_dir / "turn_events.jsonl", "".join(json.dumps(event) + "\n" for event in events))

    result = summarize_solution_latency(run_dir, verify_exit=0, hidden_exit=0)

    assert result["solution_latency_observable"] is True
    assert result["actual_turns"] == 10
    assert result["first_green_turn"] == 4
    assert result["turns_after_first_green"] == 6
    assert result["permission_denials_after_first_green"] == 2
    assert result["solution_latency_source"] == "turn_events.jsonl"


def test_solution_latency_reports_phase_not_run(tmp_path: Path):
    run_dir = tmp_path / "run"
    result = summarize_solution_latency(run_dir, verify_exit="not_run", hidden_exit="not_run")

    assert result["solution_latency_observable"] is False
    assert result["actual_turns"] is None
    assert result["first_green_turn"] is None
    assert result["turns_after_first_green"] is None
    assert result["solution_latency_note"] == "phase_not_run"
