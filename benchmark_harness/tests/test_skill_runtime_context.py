from __future__ import annotations

import re
from pathlib import Path

import pytest

from benchmark_harness.skill_runtime_context import build_skill_runtime_context


def _write_metadata(plugin_dir: Path, sha: str) -> None:
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "PINNED_SKILL_REPO.md").write_text(
        "\n".join(
            [
                "# Pinned Skill Repo",
                "",
                "- Repo URL: https://github.com/tmusser/ai-engineering-skills.git",
                f"- Pinned commit SHA: {sha}",
                "- Local path: local_plugins/ai-engineering-skills",
                "- Install command: ./benchmark_harness/scripts/pin_skill_repos.sh local_plugins",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_build_skill_runtime_context_writes_workspace_local_file(tmp_path: Path):
    plugin_dir = tmp_path / "local_plugins" / "ai-engineering-skills"
    _write_metadata(plugin_dir, "0123456789abcdef0123456789abcdef01234567")
    workspace = tmp_path / "benchmark-data" / "workspaces" / "run1" / "repo"

    context_path = build_skill_runtime_context(
        workspace_root=workspace,
        plugin_dir=str(plugin_dir),
        task_slug="06-activation-metric-migration",
        arm_slug="E-ai-engineering-skills",
        run_id="v06pilot_06-activation_E_context_smoke",
    )

    text = context_path.read_text(encoding="utf-8")

    assert context_path == workspace / ".benchmark" / "SKILL_RUNTIME_CONTEXT.md"
    assert "- Repo URL: https://github.com/tmusser/ai-engineering-skills.git" in text
    assert "- Pinned commit SHA: 0123456789abcdef0123456789abcdef01234567" in text
    assert "- Local plugin path: local_plugins/ai-engineering-skills" in text
    assert f"- Agent-visible plugin path: {plugin_dir}" in text
    assert "- Pin command: ./benchmark_harness/scripts/pin_skill_repos.sh local_plugins" in text
    assert f"- Pre-run availability check command: test -f {plugin_dir / 'PINNED_SKILL_REPO.md'}" in text
    assert "- Pre-run availability check result: available" in text
    assert f"- Pre-run availability evidence path: {workspace / '.benchmark' / 'SKILL_RUNTIME_CONTEXT.md'}" in text
    assert "- Task slug: 06-activation-metric-migration" in text
    assert "- Arm slug: E-ai-engineering-skills" in text
    assert "- Run ID: v06pilot_06-activation_E_context_smoke" in text
    assert re.search(r"(?m)^- Pinned commit SHA: [0-9a-f]{40}$", text)


def test_build_skill_runtime_context_rejects_bad_sha(tmp_path: Path):
    plugin_dir = tmp_path / "local_plugins" / "ai-engineering-skills"
    _write_metadata(plugin_dir, "not-a-real-sha")
    workspace = tmp_path / "benchmark-data" / "workspaces" / "run1" / "repo"

    with pytest.raises(ValueError, match="40-character lowercase hex SHA"):
        build_skill_runtime_context(
            workspace_root=workspace,
            plugin_dir=str(plugin_dir),
            task_slug="06-activation-metric-migration",
            arm_slug="E-ai-engineering-skills",
            run_id="v06pilot_06-activation_E_context_smoke",
        )
