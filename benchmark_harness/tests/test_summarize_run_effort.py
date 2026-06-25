from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_summarize_run_effort_cli_reads_json_and_text_metrics(tmp_path: Path):
    root = tmp_path / "benchmark-data"
    run_json = root / "runs" / "v06pilot_06-activation_E_r2" / "run_metrics.json"
    _write(
        run_json,
        json.dumps(
            {
                "run_id": "v06pilot_06-activation_E_r2",
                "label": "initial",
                "arm_slug": "E-ai-engineering-skills",
                "model": "sonnet",
                "max_turns": 60,
                "claude_exit_code": 0,
                "reached_max_turns": False,
                "wall_clock_seconds": 12.5,
                "stdout_lines": 2,
                "stderr_lines": 1,
            },
            indent=2,
        )
        + "\n",
    )
    _write(run_json.parent / "diff.patch", "diff --git a/a b/a\n")
    _write(run_json.parent / "verification_final.txt", "verify_exit=0\n")
    _write(run_json.parent / "hidden_evaluator_final.txt", "hidden_evaluator_exit=0\n")

    run_txt = root / "resume-runs" / "v06pilot_06-activation_B_r1_full_r2" / "run_metrics.txt"
    _write(
        run_txt,
        "\n".join(
            [
                "run_id: v06pilot_06-activation_B_r1_full_r2",
                "label: full resume",
                "arm_slug: B-strong-no-skill",
                "model: sonnet",
                "max_turns: 60",
                "claude_exit_code: 0",
                "reached_max_turns: true",
                "wall_clock_seconds: 43.2",
                "stdout_lines: 5",
                "stderr_lines: 0",
            ]
        )
        + "\n",
    )
    _write(run_txt.parent / "verification.txt", "verification_exit=1\n")
    _write(run_txt.parent / "hidden_evaluator.txt", "HIDDEN CONTRACT FAILED: missing resume artifacts\n")

    result = subprocess.run(
        [sys.executable, "-m", "benchmark_harness.summarize_run_effort", str(root / "runs"), str(root / "resume-runs")],
        check=True,
        capture_output=True,
        text=True,
    )

    rows = list(csv.DictReader(result.stdout.splitlines()))
    assert [row["run_id"] for row in rows] == [
        "v06pilot_06-activation_B_r1_full_r2",
        "v06pilot_06-activation_E_r2",
    ]

    full_row = rows[0]
    initial_row = rows[1]
    assert full_row["label"] == "full resume"
    assert full_row["arm_slug"] == "B-strong-no-skill"
    assert full_row["reached_max_turns"] == "true"
    assert full_row["verification_exit"] == "1"
    assert full_row["hidden_evaluator_exit"] == "1"
    assert full_row["diff_bytes"] == ""

    assert initial_row["label"] == "initial"
    assert initial_row["arm_slug"] == "E-ai-engineering-skills"
    assert initial_row["reached_max_turns"] == "false"
    assert initial_row["verification_exit"] == "0"
    assert initial_row["hidden_evaluator_exit"] == "0"
    assert int(initial_row["diff_bytes"]) > 0
