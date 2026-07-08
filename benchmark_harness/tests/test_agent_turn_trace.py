from __future__ import annotations

import json
from pathlib import Path

from benchmark_harness.agent_turn_trace import (
    AgentTurnTraceRecorder,
    TRACE_FIDELITY_CHECKPOINT_ONLY,
    TRACE_FIDELITY_RUN_LEVEL_ONLY,
    TRACE_FIDELITY_TURN_EVENT,
    TRACE_SOURCE_CLAUDE_MTIME_POLLING,
    TRACE_SOURCE_CLAUDE_STREAM_JSON,
    TRACE_SOURCE_CODEX_JSONL,
    parse_json_records,
    process_codex_record,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _run_codex_trace(
    text: str,
    *,
    tmp_path: Path,
    repo: Path | None = None,
) -> tuple[dict[str, object], list[dict[str, object]], str]:
    recorder = AgentTurnTraceRecorder(
        run_id="run-codex",
        task_slug="01-support-sla-boundary",
        arm_slug="C-codex",
        phase="initial",
        provider="codex",
        runner="codex-cli",
        trace_source=TRACE_SOURCE_CODEX_JSONL,
        trace_fidelity=TRACE_FIDELITY_RUN_LEVEL_ONLY,
        repo_root=repo,
        jsonl_path=tmp_path / "trace.jsonl",
        summary_path=tmp_path / "summary.json",
    )

    current_turn = None
    for record in parse_json_records(text):
        current_turn = process_codex_record(recorder, record, current_turn_index=current_turn)

    summary = recorder.finalize()
    serialized = (tmp_path / "trace.jsonl").read_text(encoding="utf-8")
    rows = _load_jsonl(tmp_path / "trace.jsonl")
    return summary, rows, serialized


def test_claude_turn_trace_writes_safe_metadata_and_summary(tmp_path: Path):
    repo = tmp_path / "repo"
    run_dir = tmp_path / "run"
    repo.mkdir()
    run_dir.mkdir()
    _write(repo / "VERIFY.md", "verification note\n")

    recorder = AgentTurnTraceRecorder(
        run_id="run-1",
        task_slug="01-support-sla-boundary",
        arm_slug="A-baseline",
        phase="initial",
        provider="claude",
        runner="claude-cli",
        trace_source=TRACE_SOURCE_CLAUDE_STREAM_JSON,
        trace_fidelity=TRACE_FIDELITY_TURN_EVENT,
        repo_root=repo,
        jsonl_path=run_dir / "agent_turn_trace.jsonl",
        summary_path=run_dir / "agent_turn_trace_summary.json",
    )

    recorder.record_turn_started(
        turn_index=1,
        provider_event_type="assistant",
        message_id="msg-1",
        wall_seconds=1.25,
    )
    recorder.record_assistant_message(
        turn_index=1,
        provider_event_type="assistant",
        message_id="msg-1",
        wall_seconds=1.25,
    )
    recorder.record_tool_use(
        turn_index=1,
        provider_event_type="assistant",
        tool_use_id="toolu-1",
        tool_name="Edit",
        message_id="msg-1",
        wall_seconds=2.5,
    )
    recorder.record_tool_result(
        turn_index=1,
        provider_event_type="user",
        tool_use_id="toolu-1",
        message_id="msg-1",
        wall_seconds=3.0,
    )
    recorder.record_checkpoint(
        checkpoint_index=1,
        turn_index=1,
        provider_event_type="checkpoint",
        assistant_message_id="msg-1",
        wall_seconds=12.5,
        verify_exit=0,
        hidden_evaluator_exit=0,
        functional_green=True,
        bench_ready_green=True,
        permission_denials_delta=2,
        checkpoint_eval_errors=[],
    )

    summary = recorder.finalize()
    rows = _load_jsonl(run_dir / "agent_turn_trace.jsonl")

    assert [row["event_kind"] for row in rows] == [
        "turn_started",
        "assistant_message",
        "tool_use",
        "file_change_observed",
        "tool_result",
        "checkpoint",
    ]
    assert rows[2]["file_changing_tool"] is True
    assert rows[2]["tool_name"] == "Edit"
    assert "verification note" not in (run_dir / "agent_turn_trace.jsonl").read_text(encoding="utf-8")

    assert summary["trace_source"] == TRACE_SOURCE_CLAUDE_STREAM_JSON
    assert summary["trace_fidelity"] == TRACE_FIDELITY_TURN_EVENT
    assert summary["turns_observed"] == 1
    assert summary["assistant_messages_observed"] == 1
    assert summary["tool_uses_observed"] == 1
    assert summary["file_changing_tool_uses_observed"] == 1
    assert summary["checkpoints_observed"] == 1
    assert summary["first_functional_green_turn"] == 1
    assert summary["first_bench_ready_green_turn"] == 1
    assert summary["solution_latency_observable"] is True
    assert summary["skill_trace_present"] is False
    assert summary["raw_content_omitted"] is True


def test_claude_mtime_polling_summary_is_checkpoint_only(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    recorder = AgentTurnTraceRecorder(
        run_id="run-2",
        task_slug="01-support-sla-boundary",
        arm_slug="A-baseline",
        phase="initial",
        provider="claude",
        runner="claude-cli",
        trace_source=TRACE_SOURCE_CLAUDE_MTIME_POLLING,
        trace_fidelity=TRACE_FIDELITY_CHECKPOINT_ONLY,
        jsonl_path=run_dir / "agent_turn_trace.jsonl",
        summary_path=run_dir / "agent_turn_trace_summary.json",
    )

    recorder.record_file_change_observed(
        turn_index=1,
        provider_event_type="mtime_polling",
        checkpoint_index=1,
        wall_seconds=8.0,
        notes=["mtime checkpoint"],
    )
    recorder.record_checkpoint(
        checkpoint_index=1,
        turn_index=1,
        provider_event_type="checkpoint",
        assistant_message_id=None,
        wall_seconds=8.0,
        verify_exit=0,
        hidden_evaluator_exit=1,
        functional_green=False,
        bench_ready_green=False,
        permission_denials_delta=0,
        checkpoint_eval_errors=["hidden evaluator failed"],
    )

    summary = recorder.finalize()

    assert summary["trace_fidelity"] == TRACE_FIDELITY_CHECKPOINT_ONLY
    assert summary["trace_source"] == TRACE_SOURCE_CLAUDE_MTIME_POLLING
    assert summary["turns_observed"] == 1
    assert summary["checkpoints_observed"] == 1
    assert summary["solution_latency_observable"] is False
    assert summary["solution_latency_note"] == "observed_from_mtime_polling"


def test_codex_jsonl_parser_handles_historical_turn_sequence_and_ignores_raw_content(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "VERIFY.md", "verification note\n")

    text = "\n".join(
        [
            "not json",
            json.dumps({"type": "turn.started"}),
            json.dumps({"type": "item.completed", "item": {"type": "tool_call", "name": "shell", "id": "call_1", "input": {"command": "SECRET"}}}),
            json.dumps({"type": "turn.completed"}),
        ]
    )

    summary, rows, serialized = _run_codex_trace(text, tmp_path=tmp_path, repo=repo)

    assert summary["trace_source"] == TRACE_SOURCE_CODEX_JSONL
    assert summary["trace_fidelity"] == TRACE_FIDELITY_TURN_EVENT
    assert summary["turns_observed"] == 1
    assert summary["tool_uses_observed"] == 1
    assert summary["file_changing_tool_uses_observed"] == 0
    assert summary["solution_latency_observable"] is False
    assert "SECRET" not in serialized
    assert [row["event_kind"] for row in rows] == ["turn_started", "tool_use", "turn_completed"]
    assert rows[1]["provider_event_type"] == "item.completed"
    assert rows[1]["tool_use_id"] == "call_1"
    assert rows[1]["tool_name"] == "shell"
    assert rows[1]["file_changing_tool"] is False


def test_codex_jsonl_parser_handles_nested_event_wrapper(tmp_path: Path):
    text = "\n".join(
        [
            json.dumps({"type": "stream_event", "event": {"type": "turn.started"}}),
            json.dumps(
                {
                    "type": "stream_event",
                    "event": {
                        "type": "item.completed",
                        "item": {"type": "tool_call", "name": "shell", "id": "call_2"},
                    },
                }
            ),
            json.dumps({"type": "stream_event", "event": {"type": "turn.completed"}}),
        ]
    )

    summary, rows, serialized = _run_codex_trace(text, tmp_path=tmp_path)

    assert summary["trace_fidelity"] == TRACE_FIDELITY_TURN_EVENT
    assert summary["turns_observed"] == 1
    assert [row["event_kind"] for row in rows] == ["turn_started", "tool_use", "turn_completed"]
    assert rows[0]["provider_event_type"] == "turn.started"
    assert rows[1]["provider_event_type"] == "item.completed"
    assert rows[2]["provider_event_type"] == "turn.completed"
    assert "call_2" in serialized
    assert "stream_event" not in serialized


def test_run_level_only_codex_output_summary_has_no_turns(tmp_path: Path):
    recorder = AgentTurnTraceRecorder(
        run_id="run-4",
        task_slug="01-support-sla-boundary",
        arm_slug="C-codex",
        phase="initial",
        provider="codex",
        runner="codex-cli",
        trace_source="codex_json",
        trace_fidelity=TRACE_FIDELITY_RUN_LEVEL_ONLY,
        jsonl_path=tmp_path / "trace.jsonl",
        summary_path=tmp_path / "summary.json",
    )

    for record in parse_json_records(json.dumps({"type": "result", "num_turns": 4, "total_cost_usd": 0.1})):
        process_codex_record(recorder, record, current_turn_index=None)

    summary = recorder.finalize()

    assert summary["trace_fidelity"] == TRACE_FIDELITY_RUN_LEVEL_ONLY
    assert summary["trace_source"] == "codex_json"
    assert summary["turns_observed"] == 0
    assert summary["solution_latency_observable"] is False
    assert summary["solution_latency_source"] == "final_only_no_per_turn_trace"


def test_skill_evidence_levels_cover_trace_artifact_and_context(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(
        repo / "SKILL_TRACE.jsonl",
        "\n".join(
            [
                json.dumps({"event_type": "skill_available", "skill_name": "mini-spec"}),
                json.dumps({"event_type": "skill_considered", "skill_name": "verify-contract", "turn_index": 2}),
                json.dumps({"event_type": "skill_invoked", "skill_name": "verify-contract", "turn_index": 4}),
            ]
        )
        + "\n",
    )

    recorder = AgentTurnTraceRecorder(
        run_id="run-5",
        task_slug="01-support-sla-boundary",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        provider="claude",
        runner="claude-cli",
        trace_source=TRACE_SOURCE_CLAUDE_STREAM_JSON,
        trace_fidelity=TRACE_FIDELITY_TURN_EVENT,
        repo_root=repo,
        jsonl_path=tmp_path / "trace.jsonl",
        summary_path=tmp_path / "summary.json",
    )

    summary = recorder.finalize()

    assert summary["skill_trace_present"] is True
    assert summary["skill_trace_evidence_level"] == "agent_declared"
    assert summary["declared_invoked_skills"] == ["verify-contract"]
    assert summary["declared_events_by_turn"]["2"]["skill_considered"] == ["verify-contract"]
    assert summary["declared_events_by_turn"]["4"]["skill_invoked"] == ["verify-contract"]

    artifact_repo = tmp_path / "artifact_repo"
    artifact_repo.mkdir()
    _write(artifact_repo / "VERIFY.md", "verification note\n")

    artifact_summary = AgentTurnTraceRecorder(
        run_id="run-6",
        task_slug="01-support-sla-boundary",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        provider="claude",
        runner="claude-cli",
        trace_source=TRACE_SOURCE_CLAUDE_STREAM_JSON,
        trace_fidelity=TRACE_FIDELITY_TURN_EVENT,
        repo_root=artifact_repo,
        jsonl_path=tmp_path / "artifact_trace.jsonl",
        summary_path=tmp_path / "artifact_summary.json",
    ).finalize()

    assert artifact_summary["skill_trace_evidence_level"] == "artifact_inferred"
    assert artifact_summary["artifact_inferred_skills"] == ["verify-contract"]

    context_repo = tmp_path / "context_repo"
    context_repo.mkdir()
    _write(context_repo / ".benchmark" / "SKILL_RUNTIME_CONTEXT.md", "context only\n")

    context_summary = AgentTurnTraceRecorder(
        run_id="run-7",
        task_slug="01-support-sla-boundary",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        provider="claude",
        runner="claude-cli",
        trace_source=TRACE_SOURCE_CLAUDE_STREAM_JSON,
        trace_fidelity=TRACE_FIDELITY_TURN_EVENT,
        repo_root=context_repo,
        jsonl_path=tmp_path / "context_trace.jsonl",
        summary_path=tmp_path / "context_summary.json",
    ).finalize()

    assert context_summary["skill_trace_evidence_level"] == "availability_only"
    assert context_summary["skill_runtime_context_present"] is True
