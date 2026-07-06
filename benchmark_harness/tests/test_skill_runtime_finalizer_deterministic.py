from __future__ import annotations

from pathlib import Path

from benchmark_harness.skill_runtime_finalizer import _write_deterministic_audit_artifacts, run as run_finalizer
from benchmark_harness.validate_skill_runtime_proof import validate

VALID_SHA = "3706139b9c0c772dd4cc3dfc7ffc12855fc7018c"


def _write(path: Path, text: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def _write_pinned_skill_metadata(plugin_dir: Path) -> None:
    _write(
        plugin_dir / "PINNED_SKILL_REPO.md",
        "\n".join(
            [
                "# Pinned Skill Repo",
                "",
                "- Repo URL: https://github.com/tmusser/ai-engineering-skills.git",
                f"- Pinned commit SHA: {VALID_SHA}",
                "- Local path: local_plugins/ai-engineering-skills",
                "- Install command: ./benchmark_harness/scripts/pin_skill_repos.sh local_plugins",
                "",
            ]
        ),
    )


def test_deterministic_finalizer_writes_valid_runtime_proof(tmp_path: Path):
    repo = tmp_path / "repo"
    context_dir = repo / ".benchmark"
    context_dir.mkdir(parents=True)

    context_path = context_dir / "SKILL_RUNTIME_CONTEXT.md"
    context_path.write_text(
        "\n".join(
            [
                "# Skill Runtime Context",
                "",
                "- Repo URL: https://github.com/tmusser/ai-engineering-skills",
                "- Pinned commit SHA: 0123456789abcdef0123456789abcdef01234567",
                "- Local plugin path: /tmp/local_plugins/ai-engineering-skills",
                "- Agent-visible plugin path: /tmp/local_plugins/ai-engineering-skills",
                "- Pin command: ./benchmark_harness/scripts/pin_skill_repos.sh local_plugins",
                "- Pre-run availability check command: test -f /tmp/local_plugins/ai-engineering-skills/PINNED_SKILL_REPO.md",
                "- Pre-run availability check result: available",
                f"- Pre-run availability evidence path: {context_path}",
                "- Task slug: 07-dashboard-export-scope-pressure",
                "- Arm slug: E-ai-engineering-skills",
                "- Run ID: unit-run",
                "",
            ]
        ),
        encoding="utf-8",
    )

    _write_deterministic_audit_artifacts(
        snapshot_root=repo,
        run_id="unit-run",
        task_slug="07-dashboard-export-scope-pressure",
        arm_slug="E-ai-engineering-skills",
        phase="stripped_resume",
        plugin_dir="/tmp/local_plugins/ai-engineering-skills",
        main_verify_exit=0,
        main_hidden_exit=0,
    )

    proof = repo / "SKILL_RUNTIME_PROOF.md"
    verify = repo / "VERIFY.md"

    assert proof.exists()
    assert verify.exists()
    text = proof.read_text(encoding="utf-8")
    assert validate(proof) == []
    assert f"- Evidence path: {context_path}" in text
    assert ".benchmark/SKILL_RUNTIME_CONTEXT.md records skill runtime availability" in text
    assert "deterministic harness audit finalizer" in verify.read_text(encoding="utf-8")


def test_deterministic_finalizer_recovers_pinned_sha_without_context(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    workspace = repo / "workspace"
    plugin_dir = repo / "local_plugins" / "ai-engineering-skills"
    run_dir = repo / "run"
    expected_plugin_dir = repo / "local_plugins" / "ai-engineering-skills"
    workspace.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    _write(workspace / "VERIFY.sh", "#!/usr/bin/env bash\nexit 0\n", executable=True)
    _write(workspace / "VERIFY.md", "Run VERIFY.sh and record the result.\n")
    _write_pinned_skill_metadata(plugin_dir)

    monkeypatch.setenv("ENABLE_SKILL_RUNTIME_FINALIZER", "1")
    monkeypatch.setattr(
        "benchmark_harness.skill_runtime_finalizer.PROJECT_ROOT",
        repo,
        raising=False,
    )

    def fake_run_verify(snapshot_root: Path, output_path: Path) -> int:
        _write(output_path, "verify ok\n")
        return 0

    def fake_run_hidden(snapshot_root: Path, hidden_module: str, output_path: Path) -> int:
        _write(output_path, "hidden ok\n")
        return 0

    monkeypatch.setattr("benchmark_harness.skill_runtime_finalizer._run_verify", fake_run_verify)
    monkeypatch.setattr("benchmark_harness.skill_runtime_finalizer._run_hidden", fake_run_hidden)

    exit_code = run_finalizer(
        workspace_root=workspace,
        run_dir=run_dir,
        run_id="run-1",
        task_slug="07-dashboard-export-scope-pressure",
        arm_slug="E-ai-engineering-skills",
        phase="stripped_resume",
        prompt_file=repo / "prompt.md",
        claude_cmd="claude",
        model="haiku",
        effort="low",
        max_turns=20,
        permission_mode="acceptEdits",
        plugin_dir=None,
        hidden_evaluator_module="benchmark_harness.evaluators.task7_hidden_evaluator",
        main_verify_exit=0,
        main_hidden_exit=0,
    )

    proof = workspace / "SKILL_RUNTIME_PROOF.md"
    verify = workspace / "VERIFY.md"

    assert exit_code == 0
    assert proof.exists()
    assert verify.exists()
    assert validate(proof) == []
    text = proof.read_text(encoding="utf-8")
    assert f"- Pinned commit SHA: {VALID_SHA}" in text
    assert f"- Command run: test -f {expected_plugin_dir / 'PINNED_SKILL_REPO.md'}" in text
    assert f"- Evidence path: {expected_plugin_dir / 'PINNED_SKILL_REPO.md'}" in text
    assert f"{expected_plugin_dir / 'PINNED_SKILL_REPO.md'} records the pinned skill metadata" in text
    assert ".benchmark/SKILL_RUNTIME_CONTEXT.md records skill runtime availability" not in text
