from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark_harness import telemetry


def test_emit_writes_metadata_only_jsonl(tmp_path: Path):
    out = tmp_path / "telemetry.jsonl"

    event = telemetry.emit(
        out,
        "harness.stage",
        run_id="run-1",
        task_slug="01-support-sla-boundary",
        arm_slug="A-baseline",
        phase="initial",
        fields={"exit_code": 0, "artifact_path": "VERIFY.md"},
    )

    assert event["schema_version"] == 1
    loaded = telemetry.read_events(out)
    assert loaded[0]["event_type"] == "harness.stage"
    assert loaded[0]["fields"]["exit_code"] == 0
    assert loaded[0]["fields"]["artifact_path"] == "VERIFY.md"


def test_rejects_content_like_field_names(tmp_path: Path):
    with pytest.raises(ValueError, match="content-like"):
        telemetry.emit(
            tmp_path / "telemetry.jsonl",
            "unsafe",
            fields={"prompt_body": "do not capture this"},
        )


def test_allows_content_metadata_counts(tmp_path: Path):
    out = tmp_path / "telemetry.jsonl"

    telemetry.emit(
        out,
        "llm_call.summary",
        fields={"stdout_bytes": 120, "usage_input_tokens": 42, "input_tokens": 41},
    )

    loaded = telemetry.read_events(out)
    assert loaded[0]["fields"] == {"stdout_bytes": 120, "usage_input_tokens": 42, "input_tokens": 41}


def test_context_window_helpers_are_local_estimates(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TELEMETRY_CONTEXT_WINDOW_TOKENS", "1_000")

    assert telemetry.context_window_config() == (1000, "TELEMETRY_CONTEXT_WINDOW_TOKENS")
    assert telemetry.estimate_tokens_from_chars(3999) == 1000
    assert telemetry.context_pressure_status(49.99) == "low"
    assert telemetry.context_pressure_status(50.0) == "medium"
    assert telemetry.context_pressure_status(75.0) == "high"
    assert telemetry.context_pressure_status(90.0) == "critical"


def test_collect_run_uses_existing_artifacts_without_copying_contents(tmp_path: Path):
    run_id = "vtest_01_A_r1"
    run_dir = tmp_path / "benchmark-data" / "runs" / run_id
    repo_dir = tmp_path / "benchmark-data" / "workspaces" / run_id / "repo"
    run_dir.mkdir(parents=True)
    repo_dir.mkdir(parents=True)

    (run_dir / "run_metrics.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "task_slug": "01-support-sla-boundary",
                "arm_slug": "A-baseline",
                "label": "initial",
                "model": "sonnet",
                "usage_input_tokens": 123,
                "usage_output_tokens": 45,
                "stdout_bytes": 999,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "run_provenance.json").write_text(
        json.dumps(
            {
                "task_slug": "01-support-sla-boundary",
                "requested_arm_slug": "A-baseline",
                "resolved_arm_slug": "A-baseline",
                "task_prompt_sha256": "a" * 64,
                "task_prompt_path": "tasks/01-support-sla-boundary/starter_repo/TASK.md",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "claude_stdout.txt").write_text("SECRET PROMPT OR COMPLETION BODY", encoding="utf-8")
    (run_dir / "diff.patch").write_text("diff body that should not be copied", encoding="utf-8")
    (repo_dir / "VERIFY.md").write_text("verification details that should not be copied", encoding="utf-8")

    out = telemetry.collect_run(root=tmp_path, run_id=run_id)
    text = out.read_text(encoding="utf-8")

    assert "SECRET PROMPT" not in text
    assert "diff body" not in text
    assert "verification details" not in text
    assert str(tmp_path) not in text

    events = telemetry.read_events(out)
    assert [event["event_type"] for event in events] == [
        "telemetry.collect_start",
        "llm_call.summary",
        "harness.provenance",
        "context_window.status",
        "harness.outputs",
        "workflow.artifacts",
        "telemetry.collect_end",
    ]
    llm = next(event for event in events if event["event_type"] == "llm_call.summary")
    assert llm["fields"]["usage_input_tokens"] == 123
    context = next(event for event in events if event["event_type"] == "context_window.status")
    assert context["fields"]["estimator"] == "run_metrics_input_tokens"
    assert context["fields"]["input_token_field"] == "usage_input_tokens"
    assert context["fields"]["usage_input_tokens"] == 123
    assert context["fields"]["status"] == "low"
    outputs = next(event for event in events if event["event_type"] == "harness.outputs")
    assert outputs["fields"]["files"][0]["path"].endswith("diff.patch")
    collect_end = next(event for event in events if event["event_type"] == "telemetry.collect_end")
    assert collect_end["fields"]["path"] == f"benchmark-data/runs/{run_id}/telemetry.jsonl"


def test_collect_run_accepts_codex_style_input_tokens(tmp_path: Path):
    run_id = "vtest_codex"
    run_dir = tmp_path / "benchmark-data" / "runs" / run_id
    run_dir.mkdir(parents=True)

    (run_dir / "run_metrics.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "task_slug": "01-support-sla-boundary",
                "arm_slug": "C-codex",
                "label": "initial",
                "provider": "codex",
                "runner": "codex-cli",
                "runner_cmd": "codex exec with inline prompt that must not be copied",
                "model": "gpt-5.5-codex",
                "agent_exit_code": 0,
                "input_tokens": 900,
                "output_tokens": 100,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = telemetry.collect_run(root=tmp_path, run_id=run_id)
    serialized = out.read_text(encoding="utf-8")
    events = telemetry.read_events(out)

    llm = next(event for event in events if event["event_type"] == "llm_call.summary")
    assert llm["arm_slug"] == "C-codex"
    assert llm["fields"]["provider"] == "codex"
    assert llm["fields"]["runner"] == "codex-cli"
    assert "runner_cmd" not in llm["fields"]
    assert "inline prompt" not in serialized
    assert llm["fields"]["agent_exit_code"] == 0
    assert llm["fields"]["input_tokens"] == 900
    assert llm["fields"]["output_tokens"] == 100

    context = next(event for event in events if event["event_type"] == "context_window.status")
    assert context["arm_slug"] == "C-codex"
    assert context["fields"]["estimator"] == "run_metrics_input_tokens"
    assert context["fields"]["input_token_field"] == "input_tokens"
    assert context["fields"]["input_tokens"] == 900
    assert context["fields"]["status"] == "low"
    assert context["fields"]["is_estimate"] is False


def test_collect_run_estimates_context_from_local_input_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    run_id = "vtest_context"
    run_dir = tmp_path / "benchmark-data" / "runs" / run_id
    run_dir.mkdir(parents=True)
    monkeypatch.setenv("TELEMETRY_CONTEXT_WINDOW_TOKENS", "1000")

    (run_dir / "run_metrics.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "task_slug": "01-support-sla-boundary",
                "arm_slug": "A-baseline",
                "label": "initial",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "prompt.md").write_text("local prompt body " * 240, encoding="utf-8")

    out = telemetry.collect_run(root=tmp_path, run_id=run_id)
    serialized = out.read_text(encoding="utf-8")
    assert "local prompt body" not in serialized

    context = next(event for event in telemetry.read_events(out) if event["event_type"] == "context_window.status")
    fields = context["fields"]
    assert fields["estimator"] == "local_chars_div_4"
    assert fields["context_window_tokens"] == 1000
    assert fields["context_window_source"] == "TELEMETRY_CONTEXT_WINDOW_TOKENS"
    assert fields["estimated_input_tokens"] == 1080
    assert fields["context_window_used_pct"] == 108.0
    assert fields["remaining_context_window_tokens"] == 0
    assert fields["status"] == "critical"
    assert fields["is_estimate"] is True
    assert fields["input_file_path"] == f"benchmark-data/runs/{run_id}/prompt.md"


def test_collect_run_sanitizes_absolute_provenance_paths(tmp_path: Path):
    run_id = "vtest_paths"
    run_dir = tmp_path / "benchmark-data" / "runs" / run_id
    run_dir.mkdir(parents=True)
    outside = tmp_path.parent / "secret-user" / "TASK.md"

    (run_dir / "run_provenance.json").write_text(
        json.dumps(
            {
                "task_slug": "01-support-sla-boundary",
                "resolved_arm_slug": "A-baseline",
                "task_prompt_path": str(tmp_path / "tasks" / "01" / "TASK.md"),
                "resume_prompt_path": str(outside),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = telemetry.collect_run(root=tmp_path, run_id=run_id)
    serialized = out.read_text(encoding="utf-8")

    assert str(tmp_path) not in serialized
    assert "secret-user" not in serialized
    provenance = next(event for event in telemetry.read_events(out) if event["event_type"] == "harness.provenance")
    assert provenance["fields"]["task_prompt_path"] == "tasks/01/TASK.md"
    assert provenance["fields"]["resume_prompt_path"] == "[outside-root]/TASK.md"


def test_collect_run_ignores_malformed_json_metadata(tmp_path: Path):
    run_id = "vtest_bad_json"
    run_dir = tmp_path / "benchmark-data" / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run_metrics.json").write_text("{not valid json", encoding="utf-8")

    out = telemetry.collect_run(root=tmp_path, run_id=run_id)

    assert [event["event_type"] for event in telemetry.read_events(out)] == [
        "telemetry.collect_start",
        "telemetry.collect_end",
    ]


def test_is_enabled_accepts_common_truthy_values():
    assert telemetry.is_enabled({"ENABLE_TELEMETRY": "1"}) is True
    assert telemetry.is_enabled({"ENABLE_TELEMETRY": "true"}) is True
    assert telemetry.is_enabled({"ENABLE_TELEMETRY": "0"}) is False
