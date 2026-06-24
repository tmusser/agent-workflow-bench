from __future__ import annotations

import json
from pathlib import Path

import yaml

from benchmark_harness.create_resume_workspace import create_resume_workspace


def write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_source_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "source"
    repo.mkdir()
    write(repo / "TASK.md", "task")
    write(repo / "src" / "pkg" / "module.py", "print('x')")
    write(repo / "HANDOFF.md", "handoff")
    manifest = {
        "required_outputs": [],
        "workflow_artifact_patterns": ["HANDOFF.md"],
        "strip_timing": {"forbidden_after_resume_outputs": True},
    }
    write(repo / "task_output_manifest.yml", yaml.safe_dump(manifest))
    return repo


def test_full_workspace_manifest_is_external(tmp_path: Path):
    source = make_source_repo(tmp_path)
    dest = tmp_path / "resume-workspaces" / "run1" / "full" / "repo"

    create_resume_workspace(source, dest, "full")

    manifest = dest.parent / "metadata" / "resume_workspace_manifest.json"
    assert manifest.exists()
    assert not (dest / "resume_workspace_manifest.json").exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["condition"] == "full"
    assert data["condition_undisclosed_to_agent"] is True


def test_stripped_workspace_manifests_are_external(tmp_path: Path):
    source = make_source_repo(tmp_path)
    dest = tmp_path / "resume-workspaces" / "run1" / "stripped" / "repo"
    manifest = source / "task_output_manifest.yml"

    create_resume_workspace(source, dest, "artifact_stripped", manifest=manifest)

    metadata_dir = dest.parent / "metadata"
    assert (metadata_dir / "resume_workspace_manifest.json").exists()
    assert (metadata_dir / "stripped_artifacts_manifest.json").exists()
    assert not (dest / "resume_workspace_manifest.json").exists()
    assert not (dest / "stripped_artifacts_manifest.json").exists()
    assert not (dest / "HANDOFF.md").exists()


def test_resume_workspace_copy_ignores_egg_info_noise(tmp_path: Path):
    source = make_source_repo(tmp_path)
    write(source / "src" / "churn_bugfix.egg-info" / "PKG-INFO", "generated metadata")
    dest = tmp_path / "resume-workspaces" / "run1" / "full" / "repo"

    create_resume_workspace(source, dest, "full")

    assert not any(path.name.endswith(".egg-info") for path in dest.rglob("*"))
