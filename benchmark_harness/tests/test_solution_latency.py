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
    assert result["final_turns"] == 21
    assert result["first_green_turn"] is None
    assert result["first_functional_green_turn"] is None
    assert result["first_bench_ready_green_turn"] is None
    assert result["turns_after_first_green"] is None
    assert result["turns_after_first_functional_green"] is None
    assert result["turns_after_first_bench_ready_green"] is None
    assert result["checkpoint_count"] == 0
    assert result["checkpoint_eval_errors"] == []
    assert result["solution_latency_note"] == "not_observable"
    assert result["solution_latency_source"] == "final_only_no_per_turn_trace"


def test_solution_latency_reads_explicit_summary(tmp_path: Path):
    run_dir = tmp_path / "run"
    write(run_dir / "run_metrics.json", json.dumps({"actual_turns": 21}) + "\n")
    write(
        run_dir / "solution_latency.json",
        json.dumps(
            {
                "final_turns": 21,
                "first_functional_green_turn": 7,
                "first_bench_ready_green_turn": 9,
                "turns_after_first_functional_green": 14,
                "turns_after_first_bench_ready_green": 12,
                "permission_denials_after_first_green": 3,
                "checkpoint_count": 4,
                "checkpoint_eval_errors": [],
                "observable": True,
                "source": "stream_json",
                "note": "computed_by_harness",
            }
        )
        + "\n",
    )

    result = summarize_solution_latency(run_dir, verify_exit=0, hidden_exit=0)

    assert result["solution_latency_observable"] is True
    assert result["actual_turns"] == 21
    assert result["final_turns"] == 21
    assert result["first_green_turn"] == 7
    assert result["first_functional_green_turn"] == 7
    assert result["first_bench_ready_green_turn"] == 9
    assert result["turns_after_first_green"] == 14
    assert result["turns_after_first_functional_green"] == 14
    assert result["turns_after_first_bench_ready_green"] == 12
    assert result["permission_denials_after_first_green"] == 3
    assert result["checkpoint_count"] == 4
    assert result["checkpoint_eval_errors"] == []
    assert result["solution_latency_source"] == "stream_json"
    assert result["solution_latency_note"] == "computed_by_harness"


def test_solution_latency_reads_emitted_final_only_summary(tmp_path: Path):
    run_dir = tmp_path / "run"
    write(run_dir / "run_metrics.json", json.dumps({"actual_turns": 21}) + "\n")
    write(
        run_dir / "solution_latency.json",
        json.dumps(
            {
                "actual_turns": 21,
                "final_turns": 21,
                "final_green": True,
                "first_green_turn": None,
                "first_functional_green_turn": None,
                "first_bench_ready_green_turn": None,
                "turns_after_first_functional_green": None,
                "turns_after_first_bench_ready_green": None,
                "solution_latency_observable": False,
                "observable": False,
                "source": "final_only_no_per_turn_trace",
                "note": "final_only_no_per_turn_trace",
            }
        )
        + "\n",
    )

    result = summarize_solution_latency(run_dir, verify_exit=0, hidden_exit=0)

    assert result["solution_latency_observable"] is False
    assert result["actual_turns"] == 21
    assert result["final_turns"] == 21
    assert result["first_green_turn"] is None
    assert result["first_functional_green_turn"] is None
    assert result["first_bench_ready_green_turn"] is None
    assert result["turns_after_first_green"] is None
    assert result["turns_after_first_functional_green"] is None
    assert result["turns_after_first_bench_ready_green"] is None
    assert result["solution_latency_source"] == "final_only_no_per_turn_trace"
    assert result["solution_latency_note"] == "final_only_no_per_turn_trace"


def test_solution_latency_reads_jsonl_turn_events(tmp_path: Path):
    run_dir = tmp_path / "run"
    write(run_dir / "run_metrics.json", json.dumps({"actual_turns": 10}) + "\n")
    events = [
        {"turn": 1, "verify_exit": 1, "hidden_evaluator_exit": 1, "functional_green": False, "bench_ready_green": False, "wall_seconds": 1.5, "source": "stream_json"},
        {"turn": 4, "verify_exit": 0, "hidden_evaluator_exit": 0, "functional_green": True, "bench_ready_green": False, "wall_seconds": 4.5, "permission_denials_delta": 1, "source": "stream_json"},
        {"turn": 8, "verify_exit": 0, "hidden_evaluator_exit": 0, "functional_green": True, "bench_ready_green": True, "wall_seconds": 8.5, "permission_denied": True, "permission_denials_delta": 2, "source": "stream_json"},
    ]
    write(run_dir / "turn_events.jsonl", "".join(json.dumps(event) + "\n" for event in events))

    result = summarize_solution_latency(run_dir, verify_exit=0, hidden_exit=0)

    assert result["solution_latency_observable"] is True
    assert result["actual_turns"] == 10
    assert result["final_turns"] == 10
    assert result["first_green_turn"] == 4
    assert result["first_functional_green_turn"] == 4
    assert result["first_functional_green_wall_seconds"] == 4.5
    assert result["first_bench_ready_green_turn"] == 8
    assert result["first_bench_ready_green_wall_seconds"] == 8.5
    assert result["turns_after_first_green"] == 6
    assert result["turns_after_first_functional_green"] == 6
    assert result["turns_after_first_bench_ready_green"] == 2
    assert result["permission_denials_after_first_green"] == 2
    assert result["checkpoint_count"] == 3
    assert result["solution_latency_source"] == "stream_json"


def test_solution_latency_reports_phase_not_run(tmp_path: Path):
    run_dir = tmp_path / "run"
    result = summarize_solution_latency(run_dir, verify_exit="not_run", hidden_exit="not_run")

    assert result["solution_latency_observable"] is False
    assert result["actual_turns"] is None
    assert result["first_green_turn"] is None
    assert result["turns_after_first_green"] is None
    assert result["solution_latency_note"] == "phase_not_run"
