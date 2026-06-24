from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from benchmark_harness.strip_workflow_artifacts import strip_workflow_artifacts


def write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_manifest(repo: Path, required_outputs: list[str] | None = None) -> Path:
    manifest = {
        "required_outputs": required_outputs or [],
        "workflow_artifact_patterns": [
            "SPEC.md",
            "PLAN.md",
            "HANDOFF.md",
        "VERIFY.md",
        "BUGS.md",
        "BUGFIX_REVIEW.md",
        "SKILL_RUNTIME_PROOF.md",
        "docs/*bug*.md",
    ],
        "strip_timing": {
            "allowed_phase": "before_resume_run_only",
            "forbidden_after_resume_outputs": True,
        },
    }
    path = repo / "task_output_manifest.yml"
    path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    return path


def out_path(tmp_path: Path) -> Path:
    return tmp_path / "metadata" / "stripped_artifacts_manifest.json"


def test_removes_known_workflow_artifacts(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(repo / "HANDOFF.md")
    write(repo / "SPEC.md")
    write(repo / "SKILL_RUNTIME_PROOF.md")
    manifest = make_manifest(repo)

    result = strip_workflow_artifacts(repo, manifest, out_path(tmp_path))

    assert "HANDOFF.md" in result.removed
    assert "SPEC.md" in result.removed
    assert "SKILL_RUNTIME_PROOF.md" in result.removed
    assert not (repo / "HANDOFF.md").exists()
    assert not (repo / "SPEC.md").exists()
    assert not (repo / "SKILL_RUNTIME_PROOF.md").exists()


def test_does_not_remove_source_files(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(repo / "src" / "churncalc" / "metrics.py")
    write(repo / "HANDOFF.md")
    manifest = make_manifest(repo)

    strip_workflow_artifacts(repo, manifest, out_path(tmp_path))

    assert (repo / "src" / "churncalc" / "metrics.py").exists()


def test_does_not_remove_tests(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(repo / "tests" / "test_bug.py")
    write(repo / "BUGS.md")
    manifest = make_manifest(repo)

    strip_workflow_artifacts(repo, manifest, out_path(tmp_path))

    assert (repo / "tests" / "test_bug.py").exists()


def test_does_not_remove_required_markdown_outputs(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(repo / "reports" / "bayes_summary.md")
    write(repo / "HANDOFF.md")
    manifest = make_manifest(repo, required_outputs=["reports/bayes_summary.md"])

    result = strip_workflow_artifacts(repo, manifest, out_path(tmp_path))

    assert (repo / "reports" / "bayes_summary.md").exists()
    assert "reports/bayes_summary.md" in result.kept_required_outputs


def test_writes_stripped_artifacts_manifest_outside_agent_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(repo / "VERIFY.md")
    manifest = make_manifest(repo)
    external_out = out_path(tmp_path)

    strip_workflow_artifacts(repo, manifest, external_out)

    assert external_out.exists()
    assert not (repo / "stripped_artifacts_manifest.json").exists()
    data = json.loads(external_out.read_text(encoding="utf-8"))
    assert "VERIFY.md" in data["removed"]


def test_rejects_output_manifest_inside_agent_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(repo / "VERIFY.md")
    manifest = make_manifest(repo)

    with pytest.raises(ValueError, match="outside the agent-visible repo"):
        strip_workflow_artifacts(repo, manifest, repo / "stripped_artifacts_manifest.json")


def test_keeps_ambiguous_files_and_records_reason(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(repo / "notes" / "review.md")
    manifest = make_manifest(repo)

    result = strip_workflow_artifacts(repo, manifest, out_path(tmp_path))

    assert (repo / "notes" / "review.md").exists()
    assert {"path": "notes/review.md", "reason": "ambiguous_not_removed"} in result.ambiguous_not_removed


def test_stripping_is_idempotent(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(repo / "PLAN.md")
    manifest = make_manifest(repo)
    external_out = out_path(tmp_path)

    first = strip_workflow_artifacts(repo, manifest, external_out)
    second = strip_workflow_artifacts(repo, manifest, external_out)

    assert "PLAN.md" in first.removed
    assert "PLAN.md" not in second.removed
    assert not (repo / "PLAN.md").exists()


def test_task4_bugfix_review_removed_only_before_resume(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(repo / "BUGFIX_REVIEW.md")
    write(repo / "FRESH_SESSION_REVIEW.md")
    manifest = make_manifest(repo)

    with pytest.raises(RuntimeError, match="Refusing to strip artifacts after resume outputs exist"):
        strip_workflow_artifacts(repo, manifest, out_path(tmp_path))
