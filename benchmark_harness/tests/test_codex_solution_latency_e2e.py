from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

from benchmark_harness.codex_solution_latency_observer import run


def _write(path: Path, text: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_codex_observer_finds_first_green_provider_item(tmp_path: Path):
    repo = tmp_path / "repo"
    run_dir = tmp_path / "run"
    repo.mkdir()
    _write(repo / "state.txt", "starter\n")
    _write(
        repo / "VERIFY.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\n[[ \"$(cat state.txt)\" == \"green\" ]]\n",
        executable=True,
    )
    fake_codex = tmp_path / "fake_codex.py"
    _write(
        fake_codex,
        """from __future__ import annotations
import json
import pathlib
import time

root = pathlib.Path.cwd()
print(json.dumps({"type": "turn.started"}), flush=True)
(root / "state.txt").write_text("red\\n", encoding="utf-8")
print(json.dumps({"type": "item.started", "item": {"id": "edit-red", "type": "file_change", "status": "in_progress", "changes": [{"path": "state.txt"}]}}), flush=True)
print(json.dumps({"type": "item.completed", "item": {"id": "edit-red", "type": "file_change", "status": "completed", "changes": [{"path": "state.txt"}]}}), flush=True)
time.sleep(0.25)
(root / "state.txt").write_text("green\\n", encoding="utf-8")
print(json.dumps({"type": "item.started", "item": {"id": "edit-green", "type": "file_change", "status": "in_progress", "changes": [{"path": "state.txt"}]}}), flush=True)
print(json.dumps({"type": "item.completed", "item": {"id": "edit-green", "type": "file_change", "status": "completed", "changes": [{"path": "state.txt"}]}}), flush=True)
time.sleep(0.25)
print(json.dumps({"type": "turn.completed"}), flush=True)
""",
    )
    command_json = tmp_path / "command.json"
    command_json.write_text(json.dumps([sys.executable, str(fake_codex)]), encoding="utf-8")
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("do the task\n", encoding="utf-8")

    exit_code = run(
        repo_root=repo,
        run_dir=run_dir,
        run_id="fake-codex-run",
        task_slug="04-impossible-churn",
        arm_slug="C-codex",
        phase="initial",
        prompt_file=prompt_file,
        prompt_mode="arg",
        command_json=command_json,
        hidden_evaluator_module="benchmark_harness.tests.fake_hidden_evaluator",
        max_checkpoints=8,
    )

    assert exit_code == 0
    summary = json.loads((run_dir / "agent_turn_trace_summary.json").read_text(encoding="utf-8"))
    assert summary["checkpoint_coverage_complete"] is (os.name == "posix")
    assert summary["workspace_states_observed"] == 2
    assert summary["workspace_states_skipped"] == 0
    assert summary["first_functional_green_item"] == 2
    assert summary["first_bench_ready_green_item"] == 2
    assert summary["items_after_first_functional_green"] == 0
    assert summary["solution_latency_source"] == "codex_workspace_snapshots"
    assert (run_dir / "solution_latency_checkpoints" / "checkpoint_0001" / "verification.txt").exists()
    assert (run_dir / "solution_latency_checkpoints" / "checkpoint_0002" / "hidden_evaluator.txt").exists()
    timing = json.loads((run_dir / "codex_checkpoint_timing.json").read_text(encoding="utf-8"))
    assert timing["evaluator_wall_seconds"] >= 0
    assert timing["process_end_ns"] >= timing["process_start_ns"]
