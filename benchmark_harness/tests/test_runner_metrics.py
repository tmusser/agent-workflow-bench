from __future__ import annotations

import json
from pathlib import Path

from benchmark_harness import runner_metrics


def test_runner_metrics_writes_provider_neutral_codex_metadata(tmp_path: Path):
    stdout = tmp_path / "stdout.txt"
    stderr = tmp_path / "stderr.txt"
    stdout.write_text(
        json.dumps(
            {
                "usage": {
                    "input_tokens": 900,
                    "output_tokens": 100,
                    "reasoning_tokens": 42,
                    "total_tokens": 1042,
                },
                "duration_ms": 1234,
                "stop_reason": "end_turn",
            }
        ),
        encoding="utf-8",
    )
    stderr.write_text("", encoding="utf-8")
    out = tmp_path / "run_metrics.json"

    data = runner_metrics.write_run_metrics(
        out,
        run_id="vtest_codex",
        task_slug="01-support-sla-boundary",
        arm_slug="C-codex",
        label="initial",
        provider="codex",
        runner="codex-cli",
        model="codex-default",
        exit_code=0,
        start_ns=1_000_000_000,
        end_ns=2_500_000_000,
        stdout_path=stdout,
        stderr_path=stderr,
        output_format="json",
        effort="low",
        max_turns="20",
        permission_mode="workspace-write",
    )

    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded == data
    assert loaded["provider"] == "codex"
    assert loaded["runner"] == "codex-cli"
    assert loaded["codex_exit_code"] == 0
    assert loaded["runner_exit_code"] == 0
    assert loaded["agent_exit_code"] == 0
    assert loaded["input_tokens"] == 900
    assert loaded["output_tokens"] == 100
    assert loaded["reasoning_tokens"] == 42
    assert loaded["total_tokens"] == 1042
    assert loaded["duration_ms"] == 1234
    assert loaded["reached_max_turns"] is False
    assert loaded["wall_clock_seconds"] == 1.5


def test_runner_metrics_does_not_copy_stdout_or_command_content(tmp_path: Path):
    stdout = tmp_path / "stdout.txt"
    stderr = tmp_path / "stderr.txt"
    stdout.write_text("SECRET PROMPT BODY should not be copied", encoding="utf-8")
    stderr.write_text("diff body should not be copied", encoding="utf-8")
    out = tmp_path / "run_metrics.json"

    runner_metrics.write_run_metrics(
        out,
        run_id="vtest",
        task_slug="01-support-sla-boundary",
        arm_slug="C-codex",
        label="initial",
        provider="codex",
        runner="codex-cli",
        model="codex-default",
        exit_code=1,
        start_ns=0,
        end_ns=1_000_000_000,
        stdout_path=stdout,
        stderr_path=stderr,
        output_format="text",
    )

    serialized = out.read_text(encoding="utf-8")
    assert "SECRET PROMPT BODY" not in serialized
    assert "diff body" not in serialized
    loaded = json.loads(serialized)
    assert "runner_cmd" not in loaded
    assert "agent_cmd" not in loaded
    assert loaded["stdout_bytes"] == len("SECRET PROMPT BODY should not be copied")
    assert loaded["stderr_bytes"] == len("diff body should not be copied")


def test_runner_metrics_detects_max_turns_without_saving_logs(tmp_path: Path):
    stdout = tmp_path / "stdout.txt"
    stderr = tmp_path / "stderr.txt"
    stdout.write_text("", encoding="utf-8")
    stderr.write_text("Agent stopped because it reached max turns", encoding="utf-8")

    data = runner_metrics.build_run_metrics(
        run_id="vtest",
        task_slug="01-support-sla-boundary",
        arm_slug="C-codex",
        label="initial",
        provider="codex",
        runner="codex-cli",
        model="codex-default",
        exit_code=1,
        start_ns=0,
        end_ns=1,
        stdout_path=stdout,
        stderr_path=stderr,
    )

    assert data["reached_max_turns"] is True
    assert "Agent stopped" not in json.dumps(data)
