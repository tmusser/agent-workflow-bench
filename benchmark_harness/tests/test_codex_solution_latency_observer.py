from __future__ import annotations

import json
from pathlib import Path

from benchmark_harness.agent_turn_trace import (
    AgentTurnTraceRecorder,
    TRACE_FIDELITY_TURN_EVENT,
    TRACE_SOURCE_CODEX_JSONL,
)
from benchmark_harness.codex_solution_latency_observer import (
    CapturedWorkspace,
    _candidate_trigger,
    evaluate_captures,
    workspace_fingerprint,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_workspace_fingerprint_ignores_runtime_caches(tmp_path: Path):
    repo = tmp_path / "repo"
    _write(repo / "src" / "app.py", "value = 1\n")
    before = workspace_fingerprint(repo)

    _write(repo / ".pytest_cache" / "state", "noise\n")
    _write(repo / "__pycache__" / "app.pyc", "noise\n")
    assert workspace_fingerprint(repo) == before

    _write(repo / "src" / "app.py", "value = 2\n")
    assert workspace_fingerprint(repo) != before


def test_candidate_trigger_covers_every_completed_command_and_file_change():
    file_change = {
        "type": "item.completed",
        "item": {"id": "edit-1", "type": "file_change", "changes": [{"path": "src/app.py"}]},
    }
    test_command = {
        "type": "item.completed",
        "item": {"id": "cmd-1", "type": "command_execution", "command": "python -m pytest -q"},
    }
    inspection = {
        "type": "item.completed",
        "item": {"id": "cmd-2", "type": "command_execution", "command": "sed -n '1,80p' src/app.py"},
    }
    started = {"type": "item.started", "item": {"id": "cmd-2", "type": "command_execution"}}

    assert _candidate_trigger(file_change) == "file_change_completed"
    assert _candidate_trigger(test_command) == "command_completed:test"
    assert _candidate_trigger(inspection) == "command_completed:inspection"
    assert _candidate_trigger(started) is None


def test_captured_workspace_states_report_exact_first_green_item(tmp_path: Path):
    run_dir = tmp_path / "run"
    live_repo = tmp_path / "live"
    live_repo.mkdir()

    recorder = AgentTurnTraceRecorder(
        run_id="run-codex-green",
        task_slug="04-impossible-churn",
        arm_slug="C-codex",
        phase="initial",
        provider="codex",
        runner="codex-cli",
        trace_source=TRACE_SOURCE_CODEX_JSONL,
        trace_fidelity=TRACE_FIDELITY_TURN_EVENT,
        repo_root=live_repo,
        jsonl_path=run_dir / "agent_turn_trace.jsonl",
        summary_path=run_dir / "agent_turn_trace_summary.json",
    )
    for index in range(1, 5):
        recorder.record_provider_item(
            provider_event_type="item.completed",
            provider_item_type="file_change" if index in {1, 3} else "command_execution",
            provider_item_lifecycle="completed",
            provider_item_status="completed",
            item_id=f"item-{index}",
            turn_index=1,
            wall_seconds=float(index),
        )

    captures: list[CapturedWorkspace] = []
    for checkpoint_index, (item_index, state) in enumerate(((1, "red"), (3, "green")), start=1):
        temp_root = tmp_path / f"snapshot-{checkpoint_index}"
        snapshot_root = temp_root / "repo"
        _write(snapshot_root / "state.txt", state + "\n")
        captures.append(
            CapturedWorkspace(
                checkpoint_index=checkpoint_index,
                provider_item_index=item_index,
                trigger="file_change_completed",
                wall_seconds=float(item_index),
                fingerprint=f"fingerprint-{checkpoint_index}",
                temp_root=temp_root,
                snapshot_root=snapshot_root,
                pause_seconds=0.01,
            )
        )

    def verify_runner(snapshot_root: Path, output_path: Path) -> int:
        green = (snapshot_root / "state.txt").read_text(encoding="utf-8").strip() == "green"
        _write(output_path, f"green={green}\n")
        return 0 if green else 1

    def hidden_runner(snapshot_root: Path, output_path: Path) -> int:
        return verify_runner(snapshot_root, output_path)

    evaluate_captures(
        captures=captures,
        recorder=recorder,
        run_dir=run_dir,
        run_id="run-codex-green",
        task_slug="04-impossible-churn",
        arm_slug="C-codex",
        phase="initial",
        hidden_evaluator_module="unused",
        verify_runner=verify_runner,
        hidden_runner=hidden_runner,
    )
    summary = recorder.finalize()

    assert summary["first_functional_green_item"] == 3
    assert summary["first_bench_ready_green_item"] == 3
    assert summary["items_after_first_functional_green"] == 1
    assert summary["items_after_first_bench_ready_green"] == 1
    assert summary["functional_to_bench_ready_items"] == 0
    assert summary["item_solution_latency_observable"] is True
    assert summary["first_functional_green_turn"] == 1
    assert summary["checkpoint_count"] == 2


def test_functional_and_bench_ready_tails_are_separate(tmp_path: Path):
    recorder = AgentTurnTraceRecorder(
        run_id="run-gap",
        task_slug="07-dashboard-export",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        provider="codex",
        runner="codex-cli",
        trace_source=TRACE_SOURCE_CODEX_JSONL,
        trace_fidelity=TRACE_FIDELITY_TURN_EVENT,
    )
    for index in range(1, 7):
        recorder.record_provider_item(
            provider_event_type="item.completed",
            provider_item_type="file_change",
            provider_item_lifecycle="completed",
            provider_item_status="completed",
            item_id=f"item-{index}",
            turn_index=1,
            wall_seconds=float(index),
        )
    recorder.record_checkpoint(
        checkpoint_index=1,
        turn_index=1,
        provider_item_index=3,
        provider_event_type="workspace_snapshot",
        assistant_message_id=None,
        wall_seconds=3.0,
        verify_exit=0,
        hidden_evaluator_exit=0,
        functional_green=True,
        bench_ready_green=False,
    )
    recorder.record_checkpoint(
        checkpoint_index=2,
        turn_index=1,
        provider_item_index=5,
        provider_event_type="workspace_snapshot",
        assistant_message_id=None,
        wall_seconds=5.0,
        verify_exit=0,
        hidden_evaluator_exit=0,
        functional_green=True,
        bench_ready_green=True,
    )

    summary = recorder.finalize()
    assert summary["first_functional_green_item"] == 3
    assert summary["first_bench_ready_green_item"] == 5
    assert summary["items_after_first_functional_green"] == 3
    assert summary["items_after_first_bench_ready_green"] == 1
    assert summary["functional_to_bench_ready_items"] == 2


def test_normalized_checkpoint_artifacts_do_not_contain_snapshot_source(tmp_path: Path):
    run_dir = tmp_path / "run"
    repo = tmp_path / "repo"
    _write(repo / "state.txt", "green\n")
    recorder = AgentTurnTraceRecorder(
        run_id="run-safe",
        task_slug="01-support-sla-boundary",
        arm_slug="C-codex",
        phase="initial",
        provider="codex",
        runner="codex-cli",
        trace_source=TRACE_SOURCE_CODEX_JSONL,
        trace_fidelity=TRACE_FIDELITY_TURN_EVENT,
        jsonl_path=run_dir / "trace.jsonl",
        summary_path=run_dir / "summary.json",
    )
    recorder.record_provider_item(
        provider_event_type="item.completed",
        provider_item_type="file_change",
        provider_item_lifecycle="completed",
        provider_item_status="completed",
        item_id="edit-secret",
        turn_index=1,
        wall_seconds=1.0,
    )
    temp_root = tmp_path / "snapshot"
    snapshot_root = temp_root / "repo"
    secret = "PRIVATE_SOURCE_CONTENT"
    _write(snapshot_root / "state.txt", secret)
    capture = CapturedWorkspace(1, 1, "file_change_completed", 1.0, "fp", temp_root, snapshot_root, 0.0)

    def always_green(_: Path, output_path: Path) -> int:
        _write(output_path, "ok\n")
        return 0

    evaluate_captures(
        captures=[capture],
        recorder=recorder,
        run_dir=run_dir,
        run_id="run-safe",
        task_slug="01-support-sla-boundary",
        arm_slug="C-codex",
        phase="initial",
        hidden_evaluator_module="unused",
        verify_runner=always_green,
        hidden_runner=always_green,
    )
    recorder.finalize()

    normalized = (run_dir / "trace.jsonl").read_text(encoding="utf-8")
    assert secret not in normalized
    assert json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))["raw_content_omitted"] is True
