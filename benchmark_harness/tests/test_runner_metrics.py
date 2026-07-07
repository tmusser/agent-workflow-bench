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


def test_runner_metrics_parses_codex_jsonl_usage_events(tmp_path: Path):
    stdout = tmp_path / "stdout.txt"
    stderr = tmp_path / "stderr.txt"
    stdout.write_text(
        "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "thread-123"}),
                json.dumps({"type": "turn.started"}),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"id": "item_0", "type": "agent_message", "text": "ok"},
                    }
                ),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 14891,
                            "cached_input_tokens": 8064,
                            "output_tokens": 24,
                            "reasoning_output_tokens": 17,
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    stderr.write_text("Reading additional input from stdin...\n", encoding="utf-8")

    data = runner_metrics.build_run_metrics(
        run_id="vtest_codex_jsonl",
        task_slug="01-support-sla-boundary",
        arm_slug="C-codex",
        label="initial",
        provider="codex",
        runner="codex-cli",
        model="codex-default",
        exit_code=0,
        start_ns=0,
        end_ns=2_000_000_000,
        stdout_path=stdout,
        stderr_path=stderr,
        output_format="json",
    )

    assert data["input_tokens"] == 14891
    assert data["cached_input_tokens"] == 8064
    assert data["output_tokens"] == 24
    assert data["reasoning_output_tokens"] == 17
    assert data["actual_turns"] == 1
    assert data["reached_max_turns"] is False


def test_runner_metrics_handles_invalid_json_stdout_without_copying_content(tmp_path: Path):
    stdout = tmp_path / "stdout.txt"
    stderr = tmp_path / "stderr.txt"
    stdout.write_text("{not json}\nSECRET\n", encoding="utf-8")
    stderr.write_text("", encoding="utf-8")

    data = runner_metrics.build_run_metrics(
        run_id="vtest_invalid_json",
        task_slug="01-support-sla-boundary",
        arm_slug="C-codex",
        label="initial",
        provider="codex",
        runner="codex-cli",
        model="codex-default",
        exit_code=0,
        start_ns=0,
        end_ns=1,
        stdout_path=stdout,
        stderr_path=stderr,
        output_format="json",
    )

    serialized = json.dumps(data)
    assert "SECRET" not in serialized
    assert "input_tokens" not in data
    assert data["reached_max_turns"] is False


def test_runner_metrics_uses_zero_counts_for_missing_output_files(tmp_path: Path):
    data = runner_metrics.build_run_metrics(
        run_id="vtest_missing_outputs",
        task_slug="01-support-sla-boundary",
        arm_slug="C-codex",
        label="initial",
        provider="codex",
        runner="codex-cli",
        model="codex-default",
        exit_code=7,
        start_ns=0,
        end_ns=1,
        stdout_path=tmp_path / "missing-stdout.txt",
        stderr_path=tmp_path / "missing-stderr.txt",
        output_format="text",
    )

    assert data["runner_exit_code"] == 7
    assert data["codex_exit_code"] == 7
    assert data["stdout_bytes"] == 0
    assert data["stderr_bytes"] == 0
    assert data["stdout_lines"] == 0
    assert data["stderr_lines"] == 0
    assert data["reached_max_turns"] == "unknown"
