from __future__ import annotations

import json
from pathlib import Path

from benchmark_harness.permission_denials import (
    annotate_metrics_file,
    discover_metrics_files,
    extract_from_stdout,
    extract_permission_denial_metrics,
)


def test_extract_permission_denial_metrics_counts_tools():
    metrics = extract_permission_denial_metrics(
        {
            "permission_denials": [
                {"tool_name": "Bash", "tool_use_id": "toolu_1"},
                {"tool": "Read"},
                {"name": "Bash"},
                {"irrelevant": "missing tool name"},
            ]
        }
    )

    assert metrics == {
        "permission_denials_count": 4,
        "permission_denied_tools": ["Bash", "Read"],
        "permission_denied_bash_count": 2,
    }


def test_extract_from_stdout_returns_zero_metrics_when_json_has_no_denials():
    metrics = extract_from_stdout(json.dumps({"type": "result", "num_turns": 4}))

    assert metrics == {
        "permission_denials_count": 0,
        "permission_denied_tools": [],
        "permission_denied_bash_count": 0,
    }


def test_extract_from_stdout_ignores_non_json_text():
    assert extract_from_stdout("plain text stdout") == {}


def test_annotate_metrics_file_adds_permission_fields_without_copying_tool_inputs(tmp_path: Path):
    run_dir = tmp_path / "benchmark-data" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    metrics_path = run_dir / "run_metrics.json"
    metrics_path.write_text(json.dumps({"run_id": "run-1", "model": "haiku"}) + "\n", encoding="utf-8")
    (run_dir / "claude_stdout.txt").write_text(
        json.dumps(
            {
                "type": "result",
                "permission_denials": [
                    {"tool_name": "Bash", "tool_input": {"detail": "do not copy this"}},
                    {"tool_name": "Bash", "tool_input": {"detail": "also do not copy"}},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert annotate_metrics_file(metrics_path) is True

    serialized = metrics_path.read_text(encoding="utf-8")
    loaded = json.loads(serialized)
    assert loaded["run_id"] == "run-1"
    assert loaded["model"] == "haiku"
    assert loaded["permission_denials_count"] == 2
    assert loaded["permission_denied_tools"] == ["Bash"]
    assert loaded["permission_denied_bash_count"] == 2
    assert "do not copy" not in serialized


def test_discover_metrics_files_finds_initial_and_resume_runs(tmp_path: Path):
    initial = tmp_path / "benchmark-data" / "runs" / "run-1"
    resume = tmp_path / "benchmark-data" / "resume-runs" / "run-1_full"
    initial.mkdir(parents=True)
    resume.mkdir(parents=True)
    (initial / "run_metrics.json").write_text("{}\n", encoding="utf-8")
    (resume / "run_metrics.json").write_text("{}\n", encoding="utf-8")

    assert discover_metrics_files(tmp_path) == [
        initial / "run_metrics.json",
        resume / "run_metrics.json",
    ]
