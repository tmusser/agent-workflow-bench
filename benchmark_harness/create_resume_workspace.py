from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from benchmark_harness.strip_workflow_artifacts import strip_workflow_artifacts

EXCLUDED_NAMES = {
    ".benchmark", ".ralph", "ralph_logs", "transcripts", "benchmark_prompts",
    "scoring", "evaluator", ".venv", "__pycache__", ".pytest_cache",
}


def _ignore(dir_path: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        if name in EXCLUDED_NAMES or name.endswith(".pyc") or name.endswith(".egg-info"):
            ignored.add(name)
    return ignored


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts):
        rel = path.relative_to(root).as_posix()
        h.update(rel.encode())
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def default_metadata_dir(dest_repo: Path) -> Path:
    return dest_repo.parent / "metadata" if dest_repo.name == "repo" else dest_repo.parent / f"{dest_repo.name}_metadata"


def _assert_metadata_outside_repo(repo: Path, metadata_dir: Path) -> None:
    try:
        metadata_dir.resolve().relative_to(repo.resolve())
    except ValueError:
        return
    raise ValueError("metadata_dir must be outside the agent-visible repo")


def create_resume_workspace(source_repo: Path, dest_repo: Path, condition: str, manifest: Path | None = None, metadata_dir: Path | None = None) -> dict[str, object]:
    if condition not in {"full", "artifact_stripped"}:
        raise ValueError("condition must be 'full' or 'artifact_stripped'")

    source_repo = source_repo.resolve()
    dest_repo = dest_repo.resolve()
    metadata_dir = (metadata_dir or default_metadata_dir(dest_repo)).resolve()
    _assert_metadata_outside_repo(dest_repo, metadata_dir)

    if dest_repo.exists():
        shutil.rmtree(dest_repo)
    if metadata_dir.exists():
        shutil.rmtree(metadata_dir)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_repo, dest_repo, ignore=_ignore)

    strip_result = None
    if condition == "artifact_stripped":
        if manifest is None:
            raise ValueError("artifact_stripped condition requires --manifest")
        strip_out = metadata_dir / "stripped_artifacts_manifest.json"
        strip_result = strip_workflow_artifacts(dest_repo, manifest, out_path=strip_out)

    metadata = {
        "source_repo": str(source_repo),
        "dest_repo": str(dest_repo),
        "metadata_dir": str(metadata_dir),
        "condition": condition,
        "condition_undisclosed_to_agent": True,
        "agent_visible_metadata_files": [],
        "tree_hash": tree_hash(dest_repo),
        "strip_result": asdict(strip_result) if strip_result else None,
    }
    (metadata_dir / "resume_workspace_manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a full or artifact-stripped fresh-session workspace.")
    parser.add_argument("--source-repo", required=True)
    parser.add_argument("--dest-repo", required=True)
    parser.add_argument("--condition", choices=["full", "artifact_stripped"], required=True)
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--metadata-dir", default=None, help="External metadata directory; defaults to sibling metadata/")
    args = parser.parse_args(argv)
    metadata = create_resume_workspace(
        Path(args.source_repo), Path(args.dest_repo), args.condition,
        Path(args.manifest) if args.manifest else None,
        Path(args.metadata_dir) if args.metadata_dir else None,
    )
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
