from __future__ import annotations

import json
from pathlib import Path

from benchmark_harness.emit_solution_latency import annotate_run, build_summary, write_summary


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_summary_records_final_only_boundary(tmp_path: Path):
    run_dir = tmp_path / "run"
    write(
        run_dir / "run_metrics.json",
        json.dumps(
            {
                "actual_turns": 21,
                "max_turns": 21,
                "terminal_reason": "max_turns",
                "claude_exit_code": 1,
            }
        )
        + "\n",
    )

    summary = build_summary(run_dir, phase="initial", verify_exit=0, hidden_exit=0)

    assert summary["phase"] == "initial"
    assert summary["actual_turns"] == 21
    assert summary["max_turns"] == 21
    assert summary["terminal_reason"] == "max_turns"
    assert summary["final_verify_exit"] == 0
    assert summary["final_hidden_exit"] == 0
    assert summary["final_green"] is True
    assert summary["first_green_turn"] is None
    assert summary["first_functional_green_turn"] is None
    assert summary["first_bench_ready_green_turn"] is None
    assert summary["turns_after_first_green"] is None
    assert summary["turns_after_first_functional_green"] is None
    assert summary["turns_after_first_bench_ready_green"] is None
    assert summary["solution_latency_observable"] is False
    assert summary["source"] == "final_only_no_per_turn_trace"
    assert summary["note"] == "final_only_no_per_turn_trace"


def test_write_summary_persists_json(tmp_path: Path):
    run_dir = tmp_path / "run"
    write(run_dir / "run_metrics.json", json.dumps({"actual_turns": 10}) + "\n")

    out = write_summary(run_dir, phase="stripped_resume", verify_exit=0, hidden_exit=1)

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["phase"] == "stripped_resume"
    assert data["actual_turns"] == 10
    assert data["final_green"] is False
    assert data["final_hidden_exit"] == 1
    assert data["first_functional_green_turn"] is None
    assert data["first_bench_ready_green_turn"] is None


def test_build_summary_uses_agent_turn_trace_summary(tmp_path: Path):
    run_dir = tmp_path / "run"
    write(run_dir / "run_metrics.json", json.dumps({"actual_turns": 12}) + "\n")
    write(
        run_dir / "agent_turn_trace_summary.json",
        json.dumps(
            {
                "actual_turns": 12,
                "first_functional_green_turn": 5,
                "first_bench_ready_green_turn": 8,
                "turns_after_first_functional_green": 7,
                "turns_after_first_bench_ready_green": 4,
                "permission_denials_after_first_green": 2,
                "checkpoint_count": 3,
                "checkpoint_eval_errors": [],
                "solution_latency_observable": True,
                "solution_latency_source": "codex_jsonl",
                "solution_latency_note": "observed_from_per_turn_trace",
                "trace_source": "codex_jsonl",
                "trace_fidelity": "turn_event",
            }
        )
        + "\n",
    )

    summary = build_summary(run_dir, phase="initial", verify_exit=0, hidden_exit=0)

    assert summary["solution_latency_observable"] is True
    assert summary["source"] == "codex_jsonl"
    assert summary["note"] == "observed_from_per_turn_trace"
    assert summary["first_functional_green_turn"] == 5
    assert summary["first_bench_ready_green_turn"] == 8


def test_annotate_run_writes_collected_phase_summaries(tmp_path: Path):
    root = tmp_path
    run_id = "t3_haiku_A_pr12_r1"
    initial = root / "benchmark-data" / "runs" / run_id
    full = root / "benchmark-data" / "resume-runs" / f"{run_id}_full"

    write(initial / "run_metrics.json", json.dumps({"actual_turns": 21}) + "\n")
    write(initial / "verification_final.txt", "1 passed in 0.01s\n")
    write(initial / "hidden_evaluator_final.txt", "Hidden Task 3 evaluator passed\n")

    write(full / "run_metrics.json", json.dumps({"actual_turns": 22}) + "\n")
    write(full / "verification.txt", "1 passed in 0.01s\n")
    write(full / "hidden_evaluator.txt", "Hidden Task 3 evaluator passed\n")

    written = annotate_run(root, run_id)

    assert written == [initial / "solution_latency.json", full / "solution_latency.json"]
    initial_data = json.loads((initial / "solution_latency.json").read_text(encoding="utf-8"))
    full_data = json.loads((full / "solution_latency.json").read_text(encoding="utf-8"))
    assert initial_data["phase"] == "initial"
    assert initial_data["final_green"] is True
    assert full_data["phase"] == "full_resume"
    assert full_data["actual_turns"] == 22
