from __future__ import annotations

import json
import tarfile
from pathlib import Path

from benchmark_harness import scorecard


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_bundle(tmp_path: Path, run_id: str, files: dict[str, str]) -> Path:
    root = tmp_path / f"{run_id}_bundle"
    for rel_path, text in files.items():
        write(root / rel_path, text)

    bundle = tmp_path / f"{run_id}-eval-bundle.tar.gz"
    with tarfile.open(bundle, "w:gz") as tar:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                tar.add(path, arcname=path.relative_to(root).as_posix())
    return bundle


def base_files(run_id: str) -> dict[str, str]:
    return {
        f"benchmark-data/runs/{run_id}/run_workspace_manifest.json": json.dumps(
            {"dest_repo": f"benchmark-data/workspaces/{run_id}/repo"},
            indent=2,
        )
        + "\n",
        f"benchmark-data/runs/{run_id}/run_metrics.json": json.dumps(
            {"terminal_reason": "max_turns", "actual_turns": 21},
            indent=2,
        )
        + "\n",
        f"benchmark-data/runs/{run_id}/solution_latency.json": json.dumps(
            {
                "first_green_turn": 7,
                "first_functional_green_turn": 7,
                "first_functional_green_wall_seconds": 7.5,
                "first_bench_ready_green_turn": 9,
                "first_bench_ready_green_wall_seconds": 9.5,
                "turns_after_first_green": 14,
                "turns_after_first_functional_green": 14,
                "turns_after_first_bench_ready_green": 12,
                "permission_denials_after_first_green": 3,
                "checkpoint_count": 4,
                "checkpoint_eval_errors": [],
                "observable": True,
                "source": "stream_json",
                "note": "computed_by_harness",
            },
            indent=2,
        )
        + "\n",
        f"benchmark-data/runs/{run_id}/agent_turn_trace_summary.json": json.dumps(
            {
                "trace_source": "claude_stream_json",
                "trace_fidelity": "turn_event",
                "turns_observed": 6,
                "assistant_messages_observed": 6,
                "tool_uses_observed": 14,
                "file_changing_tool_uses_observed": 4,
                "checkpoints_observed": 3,
                "first_functional_green_turn": 7,
                "first_bench_ready_green_turn": 9,
                "skill_trace_present": True,
                "skill_trace_evidence_level": "agent_declared",
                "raw_content_omitted": True,
            },
            indent=2,
        )
        + "\n",
        f"benchmark-data/runs/{run_id}/diff.patch": (
            "diff --git a/src/example.py b/src/example.py\n"
            "--- a/src/example.py\n"
            "+++ b/src/example.py\n"
            "@@\n"
            "-old\n"
            "+new\n"
        ),
        f"benchmark-data/runs/{run_id}/diff_stat.txt": "1 file changed, 1 insertion(+), 1 deletion(-)\n",
        f"benchmark-data/runs/{run_id}/verification_final.txt": "1 passed in 0.01s\n",
        f"benchmark-data/runs/{run_id}/hidden_evaluator_final.txt": "evaluator passed\n",
        f"benchmark-data/runs/{run_id}/claude_stdout.txt": "Implemented the fix.\n",
        f"benchmark-data/workspaces/{run_id}/repo/TASK.md": "# task\n",
    }


def test_scorecard_includes_solution_latency_fields(tmp_path: Path):
    run_id = "t3_haiku_A_pr12_r1"
    bundle = make_bundle(tmp_path, run_id, base_files(run_id))

    row = scorecard.score_bundle(bundle)

    assert row["initial_actual_turns"] == 21
    assert row["solution_latency_observable"] is True
    assert row["solution_latency_source"] == "stream_json"
    assert row["initial_solution_latency_observable"] is True
    assert row["initial_first_green_turn"] == 7
    assert row["initial_first_functional_green_turn"] == 7
    assert row["initial_first_functional_green_wall_seconds"] == 7.5
    assert row["initial_first_bench_ready_green_turn"] == 9
    assert row["initial_first_bench_ready_green_wall_seconds"] == 9.5
    assert row["initial_turn_trace_present"] is True
    assert row["initial_turn_trace_fidelity"] == "turn_event"
    assert row["initial_turns_observed"] == 6
    assert row["initial_file_changing_tool_uses_observed"] == 4
    assert row["initial_checkpoints_observed"] == 3
    assert row["initial_first_functional_green_turn"] == 7
    assert row["initial_first_bench_ready_green_turn"] == 9
    assert row["initial_skill_trace_evidence_level"] == "agent_declared"
    assert row["initial_turns_after_first_green"] == 14
    assert row["initial_turns_after_first_functional_green"] == 14
    assert row["initial_turns_after_first_bench_ready_green"] == 12
    assert row["initial_permission_denials_after_first_green"] == 3
    assert row["initial_solution_latency_source"] == "stream_json"
    assert row["full_turn_trace_present"] is False
    assert row["stripped_turn_trace_present"] is False
    assert row["full_resume_solution_latency_note"] == "phase_not_run"
    assert row["stripped_resume_solution_latency_note"] == "phase_not_run"
