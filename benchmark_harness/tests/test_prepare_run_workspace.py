from __future__ import annotations

import json
import subprocess
from pathlib import Path

from benchmark_harness.prepare_run_workspace import prepare_run_workspace


def write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_prepare_run_workspace_initializes_git_and_external_metadata(tmp_path: Path):
    starter = tmp_path / "starter"
    write(starter / "TASK.md", "task")
    write(starter / "src" / "pkg" / "module.py", "x = 1")
    dest = tmp_path / "workspaces" / "run1" / "repo"
    metadata_out = tmp_path / "runs" / "run1" / "run_workspace_manifest.json"

    metadata = prepare_run_workspace(starter, dest, metadata_out)

    assert (dest / ".git").exists()
    assert metadata_out.exists()
    assert metadata["git_initialized"] is True
    assert len(metadata["starter_commit"]) == 40
    assert not (dest / "run_workspace_manifest.json").exists()
    status = subprocess.check_output(["git", "status", "--short"], cwd=dest, text=True).strip()
    assert status == ""
    loaded = json.loads(metadata_out.read_text(encoding="utf-8"))
    assert loaded["starter_commit"] == metadata["starter_commit"]


def test_task4_starter_gitignore_excludes_local_noise():
    root = Path(__file__).resolve().parents[2]
    gitignore = root / "tasks" / "04-impossible-churn" / "starter_repo" / ".gitignore"

    entries = set(gitignore.read_text(encoding="utf-8").splitlines())

    assert ".venv/" in entries
    assert "__pycache__/" in entries
    assert ".pytest_cache/" in entries
    assert "*.egg-info/" in entries
    assert "build/" in entries
    assert "dist/" in entries


def test_prepare_run_workspace_ignores_egg_info_noise(tmp_path: Path):
    starter = tmp_path / "starter"
    write(starter / "TASK.md", "task")
    write(starter / "src" / "pkg" / "module.py", "x = 1")
    write(starter / "src" / "churn_bugfix.egg-info" / "PKG-INFO", "generated metadata")
    dest = tmp_path / "workspaces" / "run1" / "repo"
    metadata_out = tmp_path / "runs" / "run1" / "run_workspace_manifest.json"

    prepare_run_workspace(starter, dest, metadata_out)

    assert not any(path.name.endswith(".egg-info") for path in dest.rglob("*"))
