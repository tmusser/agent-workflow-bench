from __future__ import annotations

import json
import textwrap
from pathlib import Path

import benchmark_harness.skill_runtime_finalizer as finalizer


VALID_SHA = "0123456789abcdef0123456789abcdef01234567"


def _write(path: Path, text: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def _valid_skill_runtime_proof(run_id: str) -> str:
    return textwrap.dedent(
        f"""\
        # Skill Runtime Proof

        ## Run
        - Run ID: {run_id}
        - Arm: E-ai-engineering-skills
        - Task: 04-impossible-churn
        - Repeat: 1

        ## Skill source
        - Repo URL: https://example.com/skills.git
        - Pinned commit SHA: {VALID_SHA}
        - Local path: /tmp/skills/ai-engineering-skills
        - Install command: cp -R /tmp/skills/ai-engineering-skills ~/.claude/skills/ai-engineering-skills
        - Install stdout/stderr path: benchmark-data/runs/{run_id}/install.txt

        ## Activation
        - Agent CLI: claude
        - Activation mechanism: plugin dir mounted before run
        - Prompt wrapper path: arms/E-ai-engineering-skills.md
        - Agent-visible skill files: ~/.claude/skills/ai-engineering-skills/README.md

        ## Pre-run availability check
        - Command run: test -f ~/.claude/skills/ai-engineering-skills/README.md
        - Result: pass
        - Evidence path: benchmark-data/runs/{run_id}/skill_available.txt

        ## During-run evidence
        - Did the agent mention or invoke the skill? yes
        - Evidence: benchmark-data/runs/{run_id}/stdout.txt
        """
    )


def _prepare_workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    workspace_root = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    prompt_file = tmp_path / "prompt.md"
    workspace_root.mkdir()
    run_dir.mkdir()
    _write(
        workspace_root / "VERIFY.sh",
        "#!/usr/bin/env bash\nexit 0\n",
        executable=True,
    )
    _write(workspace_root / "VERIFY.md", "Run VERIFY.sh and record the result.\n")
    _write(workspace_root / ".benchmark" / "SKILL_RUNTIME_CONTEXT.md", "context\n")
    _write(prompt_file, "finalizer prompt\n")
    return workspace_root, run_dir, prompt_file


def _write_summary_files(out_dir: Path, *, stdout: str = "{}", stderr: str = "", exit_code: int = 0) -> dict[str, object]:
    _write(out_dir / "claude_stdout.txt", stdout)
    _write(out_dir / "claude_stderr.txt", stderr)
    _write(out_dir / "claude_exit_code.txt", f"{exit_code}\n")
    metrics = {
        "claude_exit_code": exit_code,
        "num_turns": 6,
        "total_cost_usd": 0.0187,
        "wall_clock_seconds": 12.34,
        "output_format": "json",
    }
    _write(out_dir / "run_metrics.json", json.dumps(metrics, indent=2) + "\n")
    return metrics


def test_finalizer_disabled_by_default(tmp_path: Path, monkeypatch):
    workspace_root, run_dir, prompt_file = _prepare_workspace(tmp_path)
    finalizer_dir = run_dir / "finalizer"
    monkeypatch.delenv("ENABLE_SKILL_RUNTIME_FINALIZER", raising=False)

    exit_code = finalizer.run(
        workspace_root=workspace_root,
        run_dir=finalizer_dir,
        run_id="run-1",
        task_slug="04-impossible-churn",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        prompt_file=prompt_file,
        claude_cmd="claude",
        model="haiku",
        effort="low",
        max_turns=20,
        permission_mode="acceptEdits",
        plugin_dir="/tmp/plugins",
        hidden_evaluator_module="benchmark_harness.evaluators.task4_hidden_evaluator",
        main_verify_exit=0,
        main_hidden_exit=0,
    )

    summary = json.loads((finalizer_dir / "summary.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert summary["finalizer_enabled"] is False
    assert summary["finalizer_ran"] is False
    assert summary["trigger_reason"] == "disabled"
    assert summary["finalizer_valid"] is False
    assert not (workspace_root / "SKILL_RUNTIME_PROOF.md").exists()


def test_finalizer_does_not_run_for_a_baseline(tmp_path: Path, monkeypatch):
    workspace_root, run_dir, prompt_file = _prepare_workspace(tmp_path)
    finalizer_dir = run_dir / "finalizer"
    monkeypatch.setenv("ENABLE_SKILL_RUNTIME_FINALIZER", "1")

    called = {"value": False}

    def fail_if_called(**_: object) -> dict[str, object]:
        called["value"] = True
        raise AssertionError("finalizer Claude run must not happen for A arms")

    monkeypatch.setattr(finalizer, "_run_claude", fail_if_called)

    exit_code = finalizer.run(
        workspace_root=workspace_root,
        run_dir=finalizer_dir,
        run_id="run-1",
        task_slug="04-impossible-churn",
        arm_slug="A-baseline",
        phase="initial",
        prompt_file=prompt_file,
        claude_cmd="claude",
        model="haiku",
        effort="low",
        max_turns=20,
        permission_mode="acceptEdits",
        plugin_dir=None,
        hidden_evaluator_module="benchmark_harness.evaluators.task4_hidden_evaluator",
        main_verify_exit=0,
        main_hidden_exit=0,
    )

    summary = json.loads((finalizer_dir / "summary.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert called["value"] is False
    assert summary["finalizer_ran"] is False
    assert summary["trigger_reason"] == "non_e_arm"
    assert summary["finalizer_valid"] is False


def test_finalizer_does_not_run_when_main_functional_green_is_false(tmp_path: Path, monkeypatch):
    workspace_root, run_dir, prompt_file = _prepare_workspace(tmp_path)
    finalizer_dir = run_dir / "finalizer"
    monkeypatch.setenv("ENABLE_SKILL_RUNTIME_FINALIZER", "1")

    called = {"value": False}

    def fail_if_called(**_: object) -> dict[str, object]:
        called["value"] = True
        raise AssertionError("finalizer Claude run must not happen when main is not green")

    monkeypatch.setattr(finalizer, "_run_claude", fail_if_called)

    exit_code = finalizer.run(
        workspace_root=workspace_root,
        run_dir=finalizer_dir,
        run_id="run-1",
        task_slug="04-impossible-churn",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        prompt_file=prompt_file,
        claude_cmd="claude",
        model="haiku",
        effort="low",
        max_turns=20,
        permission_mode="acceptEdits",
        plugin_dir="/tmp/plugins",
        hidden_evaluator_module="benchmark_harness.evaluators.task4_hidden_evaluator",
        main_verify_exit=1,
        main_hidden_exit=0,
    )

    summary = json.loads((finalizer_dir / "summary.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert called["value"] is False
    assert summary["finalizer_ran"] is False
    assert summary["trigger_reason"] == "main_functional_green_false"
    assert summary["finalizer_valid"] is False


def test_finalizer_skips_when_proof_is_already_valid(tmp_path: Path, monkeypatch):
    workspace_root, run_dir, prompt_file = _prepare_workspace(tmp_path)
    finalizer_dir = run_dir / "finalizer"
    _write(workspace_root / "SKILL_RUNTIME_PROOF.md", _valid_skill_runtime_proof("run-1"))
    monkeypatch.setenv("ENABLE_SKILL_RUNTIME_FINALIZER", "1")

    called = {"value": False}

    def fail_if_called(**_: object) -> dict[str, object]:
        called["value"] = True
        raise AssertionError("finalizer Claude run must not happen when proof is already valid")

    monkeypatch.setattr(finalizer, "_run_claude", fail_if_called)

    exit_code = finalizer.run(
        workspace_root=workspace_root,
        run_dir=finalizer_dir,
        run_id="run-1",
        task_slug="04-impossible-churn",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        prompt_file=prompt_file,
        claude_cmd="claude",
        model="haiku",
        effort="low",
        max_turns=20,
        permission_mode="acceptEdits",
        plugin_dir="/tmp/plugins",
        hidden_evaluator_module="benchmark_harness.evaluators.task4_hidden_evaluator",
        main_verify_exit=0,
        main_hidden_exit=0,
    )

    summary = json.loads((finalizer_dir / "summary.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert called["value"] is False
    assert summary["finalizer_ran"] is False
    assert summary["trigger_reason"] == "proof_already_valid"
    assert summary["finalizer_valid"] is True
    assert summary["bench_ready_after_finalizer"] is True


def test_finalizer_runs_when_proof_is_missing_and_copies_back_proof(tmp_path: Path, monkeypatch):
    workspace_root, run_dir, prompt_file = _prepare_workspace(tmp_path)
    finalizer_dir = run_dir / "finalizer"
    monkeypatch.setenv("ENABLE_SKILL_RUNTIME_FINALIZER", "1")

    snapshot_roots: list[Path] = []

    def fake_run_claude(**kwargs: object) -> dict[str, object]:
        snapshot_root = kwargs["snapshot_root"]
        out_dir = kwargs["out_dir"]
        assert isinstance(snapshot_root, Path)
        assert snapshot_root != workspace_root
        snapshot_roots.append(snapshot_root)
        _write(snapshot_root / "SKILL_RUNTIME_PROOF.md", _valid_skill_runtime_proof("run-1"))
        _write_summary_files(out_dir)
        return {
            "claude_exit_code": 0,
            "num_turns": 6,
            "total_cost_usd": 0.0187,
            "wall_clock_seconds": 12.34,
            "output_format": "json",
        }

    def fake_run_verify(snapshot_root: Path, output_path: Path) -> int:
        assert snapshot_root != workspace_root
        _write(output_path, "verify ok\n")
        return 0

    def fake_run_hidden(snapshot_root: Path, hidden_module: str, output_path: Path) -> int:
        assert snapshot_root != workspace_root
        assert hidden_module == "benchmark_harness.evaluators.task4_hidden_evaluator"
        _write(output_path, "hidden ok\n")
        return 0

    monkeypatch.setattr(finalizer, "_run_claude", fake_run_claude)
    monkeypatch.setattr(finalizer, "_run_verify", fake_run_verify)
    monkeypatch.setattr(finalizer, "_run_hidden", fake_run_hidden)

    exit_code = finalizer.run(
        workspace_root=workspace_root,
        run_dir=finalizer_dir,
        run_id="run-1",
        task_slug="04-impossible-churn",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        prompt_file=prompt_file,
        claude_cmd="claude",
        model="haiku",
        effort="low",
        max_turns=20,
        permission_mode="acceptEdits",
        plugin_dir="/tmp/plugins",
        hidden_evaluator_module="benchmark_harness.evaluators.task4_hidden_evaluator",
        main_verify_exit=0,
        main_hidden_exit=0,
    )

    summary = json.loads((finalizer_dir / "summary.json").read_text(encoding="utf-8"))
    audit = json.loads((finalizer_dir / "file_change_audit.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert snapshot_roots and snapshot_roots[0] != workspace_root
    assert summary["finalizer_ran"] is True
    assert summary["created_skill_runtime_proof"] is True
    assert summary["finalizer_valid"] is True
    assert summary["bench_ready_after_finalizer"] is True
    assert summary["bench_ready_via_finalizer"] is True
    assert summary["functional_files_changed"] is False
    assert summary["allowed_files_changed"] == ["SKILL_RUNTIME_PROOF.md"]
    assert summary["forbidden_files_changed"] == []
    assert summary["actual_turns"] == 6
    assert summary["total_cost_usd"] == 0.0187
    assert summary["wall_clock_seconds"] == 12.34
    assert summary["claude_exit_code"] == 0
    assert summary["validator_exit"] == 0
    assert summary["verify_after_exit"] == 0
    assert summary["hidden_after_exit"] == 0
    assert (finalizer_dir / "claude_stdout.txt").exists()
    assert (finalizer_dir / "claude_stderr.txt").exists()
    assert (finalizer_dir / "claude_exit_code.txt").exists()
    assert (finalizer_dir / "run_metrics.json").exists()
    assert (finalizer_dir / "validation.txt").exists()
    assert (finalizer_dir / "verify_after.txt").exists()
    assert (finalizer_dir / "hidden_after.txt").exists()
    assert (workspace_root / "SKILL_RUNTIME_PROOF.md").exists()
    assert not (workspace_root / "finalizer").exists()
    assert audit["functional_files_changed"] is False
    assert audit["allowed_files_changed"] == ["SKILL_RUNTIME_PROOF.md"]
    assert audit["forbidden_files_changed"] == []


def test_finalizer_invalidates_forbidden_functional_file_changes(tmp_path: Path, monkeypatch):
    workspace_root, run_dir, prompt_file = _prepare_workspace(tmp_path)
    finalizer_dir = run_dir / "finalizer"
    _write(workspace_root / "src" / "app.py", "print('main')\n")
    monkeypatch.setenv("ENABLE_SKILL_RUNTIME_FINALIZER", "1")

    def fake_run_claude(**kwargs: object) -> dict[str, object]:
        snapshot_root = kwargs["snapshot_root"]
        out_dir = kwargs["out_dir"]
        assert isinstance(snapshot_root, Path)
        _write(snapshot_root / "SKILL_RUNTIME_PROOF.md", _valid_skill_runtime_proof("run-1"))
        _write(snapshot_root / "src" / "app.py", "print('changed')\n")
        _write_summary_files(out_dir)
        return {
            "claude_exit_code": 0,
            "num_turns": 6,
            "total_cost_usd": 0.0187,
            "wall_clock_seconds": 12.34,
            "output_format": "json",
        }

    def fake_run_verify(snapshot_root: Path, output_path: Path) -> int:
        _write(output_path, "verify ok\n")
        return 0

    def fake_run_hidden(snapshot_root: Path, hidden_module: str, output_path: Path) -> int:
        _write(output_path, "hidden ok\n")
        return 0

    monkeypatch.setattr(finalizer, "_run_claude", fake_run_claude)
    monkeypatch.setattr(finalizer, "_run_verify", fake_run_verify)
    monkeypatch.setattr(finalizer, "_run_hidden", fake_run_hidden)

    exit_code = finalizer.run(
        workspace_root=workspace_root,
        run_dir=finalizer_dir,
        run_id="run-1",
        task_slug="04-impossible-churn",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        prompt_file=prompt_file,
        claude_cmd="claude",
        model="haiku",
        effort="low",
        max_turns=20,
        permission_mode="acceptEdits",
        plugin_dir="/tmp/plugins",
        hidden_evaluator_module="benchmark_harness.evaluators.task4_hidden_evaluator",
        main_verify_exit=0,
        main_hidden_exit=0,
    )

    summary = json.loads((finalizer_dir / "summary.json").read_text(encoding="utf-8"))
    audit = json.loads((finalizer_dir / "file_change_audit.json").read_text(encoding="utf-8"))
    assert exit_code == 1
    assert summary["finalizer_ran"] is True
    assert summary["finalizer_valid"] is False
    assert summary["bench_ready_after_finalizer"] is False
    assert summary["functional_files_changed"] is True
    assert "src/app.py" in summary["forbidden_files_changed"]
    assert "src/app.py" in audit["forbidden_files_changed"]
    assert not (workspace_root / "SKILL_RUNTIME_PROOF.md").exists()
