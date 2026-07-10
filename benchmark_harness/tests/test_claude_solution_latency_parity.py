from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

from benchmark_harness.claude_solution_latency_observer import run


def _write(path: Path, text: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _fake_claude_script(path: Path) -> None:
    _write(
        path,
        f"""#!{sys.executable}
from __future__ import annotations
import json
import pathlib
import time

root = pathlib.Path.cwd()
print(json.dumps({{"type": "assistant", "message": {{"id": "msg-red", "content": [{{"type": "tool_use", "id": "edit-red", "name": "Edit"}}]}}}}), flush=True)
(root / "state.txt").write_text("red\\n", encoding="utf-8")
print(json.dumps({{"type": "user", "message": {{"content": [{{"type": "tool_result", "tool_use_id": "edit-red"}}]}}}}), flush=True)
time.sleep(0.35)
print(json.dumps({{"type": "assistant", "message": {{"id": "msg-green", "content": [{{"type": "tool_use", "id": "edit-green", "name": "Edit"}}]}}}}), flush=True)
(root / "state.txt").write_text("green\\n", encoding="utf-8")
print(json.dumps({{"type": "user", "message": {{"content": [{{"type": "tool_result", "tool_use_id": "edit-green"}}]}}}}), flush=True)
time.sleep(0.35)
print(json.dumps({{"type": "result", "num_turns": 2}}), flush=True)
""",
        executable=True,
    )


def _prepare_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    run_dir = tmp_path / "run"
    repo.mkdir()
    _write(repo / "state.txt", "starter\n")
    _write(
        repo / "VERIFY.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\n[[ \"$(cat state.txt)\" == \"green\" ]]\n",
        executable=True,
    )
    prompt = tmp_path / "prompt.md"
    prompt.write_text("solve the task\n", encoding="utf-8")
    fake_claude = tmp_path / "fake-claude"
    _fake_claude_script(fake_claude)
    return repo, run_dir, prompt


def test_stream_json_observer_reports_first_green_turn_with_complete_stable_coverage(tmp_path: Path):
    repo, run_dir, prompt = _prepare_repo(tmp_path)
    fake_claude = tmp_path / "fake-claude"

    exit_code = run(
        repo_root=repo,
        run_dir=run_dir,
        run_id="claude-parity",
        task_slug="04-impossible-churn",
        arm_slug="A-baseline",
        phase="initial",
        prompt_file=prompt,
        claude_cmd=str(fake_claude),
        model="sonnet",
        effort="low",
        max_turns=20,
        permission_mode="acceptEdits",
        plugin_dir=None,
        hidden_evaluator_module="benchmark_harness.tests.fake_hidden_evaluator",
        mode="stream_json",
        max_checkpoints=8,
    )

    assert exit_code == 0
    summary = json.loads((run_dir / "agent_turn_trace_summary.json").read_text(encoding="utf-8"))
    assert summary["first_functional_green_turn"] == 2
    assert summary["first_bench_ready_green_turn"] == 2
    assert summary["workspace_states_observed"] == 2
    assert summary["workspace_states_skipped"] == 0
    assert summary["checkpoint_evaluation_deferred"] is True
    assert summary["checkpoint_boundary_resolution"] == "file_changing_tool_result_then_process_group_pause"
    assert summary["native_observation_unit"] == "assistant_turn_and_file_changing_tool_result"
    assert summary["checkpoint_coverage_complete"] is (os.name == "posix")
    assert summary["stable_snapshot_coverage_complete"] is (os.name == "posix")
    assert summary["solution_latency_observable"] is (os.name == "posix")
    assert summary["solution_latency_source"] == "claude_workspace_snapshots"

    checkpoints = run_dir / "solution_latency_checkpoints"
    assert (checkpoints / "checkpoint_0001" / "verification.txt").exists()
    assert (checkpoints / "checkpoint_0002" / "hidden_evaluator.txt").exists()
    first = json.loads((checkpoints / "checkpoint_0001" / "checkpoint.json").read_text(encoding="utf-8"))
    second = json.loads((checkpoints / "checkpoint_0002" / "checkpoint.json").read_text(encoding="utf-8"))
    assert first["functional_green"] is False
    assert second["functional_green"] is True
    assert not list(run_dir.glob("claude-first-green-*"))

    timing = json.loads((run_dir / "claude_checkpoint_timing.json").read_text(encoding="utf-8"))
    assert timing["process_end_ns"] >= timing["process_start_ns"]
    assert timing["evaluator_wall_seconds"] >= 0
    assert timing["snapshot_pause_seconds"] >= 0


def test_checkpoint_cap_marks_first_green_claim_non_conclusive(tmp_path: Path):
    repo, run_dir, prompt = _prepare_repo(tmp_path)
    fake_claude = tmp_path / "fake-claude"

    exit_code = run(
        repo_root=repo,
        run_dir=run_dir,
        run_id="claude-capped",
        task_slug="04-impossible-churn",
        arm_slug="A-baseline",
        phase="initial",
        prompt_file=prompt,
        claude_cmd=str(fake_claude),
        model="sonnet",
        effort="low",
        max_turns=20,
        permission_mode="acceptEdits",
        plugin_dir=None,
        hidden_evaluator_module="benchmark_harness.tests.fake_hidden_evaluator",
        mode="stream_json",
        max_checkpoints=1,
    )

    assert exit_code == 0
    summary = json.loads((run_dir / "agent_turn_trace_summary.json").read_text(encoding="utf-8"))
    assert summary["workspace_states_skipped"] > 0
    assert summary["checkpoint_coverage_complete"] is False
    assert summary["solution_latency_observable"] is False
    assert summary["solution_latency_note"] == "partial_workspace_snapshot_coverage"


def test_polling_mode_never_claims_complete_boundary_coverage(tmp_path: Path):
    repo, run_dir, prompt = _prepare_repo(tmp_path)
    fake_claude = tmp_path / "fake-claude"

    exit_code = run(
        repo_root=repo,
        run_dir=run_dir,
        run_id="claude-polling",
        task_slug="04-impossible-churn",
        arm_slug="A-baseline",
        phase="initial",
        prompt_file=prompt,
        claude_cmd=str(fake_claude),
        model="sonnet",
        effort="low",
        max_turns=20,
        permission_mode="acceptEdits",
        plugin_dir=None,
        hidden_evaluator_module="benchmark_harness.tests.fake_hidden_evaluator",
        mode="mtime_polling",
        max_checkpoints=8,
    )

    assert exit_code == 0
    summary = json.loads((run_dir / "agent_turn_trace_summary.json").read_text(encoding="utf-8"))
    assert summary["checkpoint_coverage_complete"] is False
    assert summary["solution_latency_observable"] is False
    assert summary["native_observation_unit"] == "sampled_workspace_state"
    assert summary["checkpoint_boundary_resolution"] == "sampled_workspace_change_then_process_group_pause"
