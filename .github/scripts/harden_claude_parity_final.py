from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one patch target, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "benchmark_harness/claude_solution_latency_observer.py",
    '''    live_captures = [item for item in captures if item.trigger != "final_workspace"]
    stable_snapshots = bool(captures) and all(item.process_group_paused for item in live_captures)
    coverage_complete = (
        bool(captures)
''',
    '''    live_captures = [item for item in captures if item.trigger != "final_workspace"]
    # A final-only snapshot can validate the terminal workspace, but it cannot
    # establish which live turn first became green. Exact stream coverage needs
    # at least one stable checkpoint captured while Claude was still running.
    stable_snapshots = bool(live_captures) and all(
        item.process_group_paused for item in live_captures
    )
    coverage_complete = (
        bool(live_captures)
''',
)

replace_once(
    "docs/capabilities.md",
    '''Claude emits assistant messages and tool results. The hardened observer captures a distinct workspace state after a completed file-changing tool result, with an assistant-boundary fallback when necessary.
''',
    '''Claude emits assistant messages and tool results. The hardened observer captures a distinct workspace state only after a completed file-changing tool result. Assistant boundaries are retained for turn accounting but are not used as snapshot fallbacks because the next turn may already be mutating the workspace when that event is consumed.
''',
)

path = Path("benchmark_harness/tests/test_claude_solution_latency_parity.py")
text = path.read_text(encoding="utf-8")
addition = r'''


def test_final_only_snapshot_does_not_claim_exact_stream_coverage(tmp_path: Path):
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
    prompt.write_text("inspect only\n", encoding="utf-8")
    fake_claude = tmp_path / "fake-claude-no-tools"
    _write(
        fake_claude,
        f"""#!{sys.executable}
from __future__ import annotations
import json
print(json.dumps({{"type": "assistant", "message": {{"id": "msg-1", "content": []}}}}), flush=True)
print(json.dumps({{"type": "result", "num_turns": 1}}), flush=True)
""",
        executable=True,
    )

    exit_code = run(
        repo_root=repo,
        run_dir=run_dir,
        run_id="claude-final-only",
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
    assert summary["workspace_states_observed"] == 1
    assert summary["checkpoint_coverage_complete"] is False
    assert summary["stable_snapshot_coverage_complete"] is False
    assert summary["solution_latency_observable"] is False
    assert summary["first_functional_green_turn"] is None
'''
if "test_final_only_snapshot_does_not_claim_exact_stream_coverage" not in text:
    path.write_text(text.rstrip() + addition.rstrip() + "\n", encoding="utf-8")
