from __future__ import annotations

import textwrap
from pathlib import Path

from benchmark_harness.solution_latency_observer import evaluate_checkpoint_snapshot, is_bench_ready_green


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _valid_skill_runtime_proof(run_id: str) -> str:
    return textwrap.dedent(
        f"""\
        # Skill Runtime Proof

        ## Run
        - Run ID: {run_id}
        - Arm: E-ai-engineering-skills
        - Task: 03-refund-grain
        - Repeat: 1

        ## Skill source
        - Repo URL: https://example.com/skills.git
        - Pinned commit SHA: 0123456789abcdef0123456789abcdef01234567
        - Local path: /tmp/skills/ai-engineering-skills
        - Install command: cp -R /tmp/skills/ai-engineering-skills ~/.claude/skills/ai-engineering-skills
        - Install stdout/stderr path: benchmark-data/runs/{run_id}/install.txt

        ## Activation
        - Agent CLI: claude
        - Activation mechanism: plugin dir mounted before run
        - Prompt wrapper path: arms/E-ai-engineering-skills.md
        - Agent-visible skill files: ~/.claude/skills/ai-engineering-skills/README.md
        - Environment variables relevant to skill loading: CLAUDE_PLUGIN_DIR=/tmp/plugins

        ## Pre-run availability check
        - Command run: test -f ~/.claude/skills/ai-engineering-skills/README.md
        - Result: pass
        - Evidence path: benchmark-data/runs/{run_id}/skill_available.txt

        ## During-run evidence
        - Did the agent mention or invoke the skill? yes
        - Evidence: benchmark-data/runs/{run_id}/stdout.txt
        - Notes: none

        ## Post-run caveat
        - Could a bad result be due to the skill not being loaded? no
        - Reviewer notes: validated locally
        """
    )


def test_e_arm_bench_ready_requires_skill_runtime_proof(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write(repo_root / "VERIFY.md", "Run VERIFY.sh and record the result.\n")

    ready, issues = is_bench_ready_green("E-ai-engineering-skills", repo_root, True)
    assert ready is False
    assert "missing SKILL_RUNTIME_PROOF.md" in issues

    proof = _valid_skill_runtime_proof("run-1")
    _write(repo_root / "SKILL_RUNTIME_PROOF.md", proof)

    ready, issues = is_bench_ready_green("E-ai-engineering-skills", repo_root, True)
    assert ready is True
    assert issues == []


def test_checkpoint_outputs_stay_outside_agent_repo(tmp_path: Path):
    repo_root = tmp_path / "repo"
    run_dir = tmp_path / "run"
    repo_root.mkdir()
    _write(repo_root / "VERIFY.md", "Run VERIFY.sh and record the result.\n")

    def verify_runner(snapshot_root: Path, output_path: Path) -> int:
        assert snapshot_root != repo_root
        _write(output_path, "verify ok\n")
        return 0

    def hidden_runner(snapshot_root: Path, output_path: Path) -> int:
        assert snapshot_root != repo_root
        _write(output_path, "hidden ok\n")
        return 0

    record = evaluate_checkpoint_snapshot(
        repo_root=repo_root,
        run_dir=run_dir,
        run_id="run-1",
        task_slug="03-refund-grain",
        arm_slug="A-baseline",
        phase="initial",
        source="stream_json",
        checkpoint_index=1,
        turn=4,
        assistant_message_id="msg-1",
        hidden_evaluator_module="benchmark_harness.evaluators.task3_hidden_evaluator",
        wall_seconds=12.5,
        verify_runner=verify_runner,
        hidden_runner=hidden_runner,
    )

    assert record["functional_green"] is True
    assert record["bench_ready_green"] is True
    assert record["source"] == "stream_json"
    assert (run_dir / "solution_latency_checkpoints" / "checkpoint_0001" / "hidden_evaluator.txt").exists()
    assert not (repo_root / "hidden_evaluator.txt").exists()
