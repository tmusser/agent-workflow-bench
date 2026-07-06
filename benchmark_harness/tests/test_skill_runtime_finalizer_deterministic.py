from __future__ import annotations

from pathlib import Path

from benchmark_harness.skill_runtime_finalizer import _write_deterministic_audit_artifacts
from benchmark_harness.validate_skill_runtime_proof import validate


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
    assert validate(proof) == []
    assert "deterministic harness audit finalizer" in verify.read_text(encoding="utf-8")
