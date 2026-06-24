from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

EXCLUDED_NAMES = {".venv", "__pycache__", ".pytest_cache", ".git"}


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


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def prepare_run_workspace(starter_repo: Path, dest_repo: Path, metadata_out: Path) -> dict[str, object]:
    starter_repo = starter_repo.resolve()
    dest_repo = dest_repo.resolve()
    metadata_out = metadata_out.resolve()

    if dest_repo.exists():
        shutil.rmtree(dest_repo)
    dest_repo.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(starter_repo, dest_repo, ignore=_ignore)

    _run(["git", "init"], cwd=dest_repo)
    _run(["git", "config", "user.email", "benchmark@example.invalid"], cwd=dest_repo)
    _run(["git", "config", "user.name", "Benchmark Runner"], cwd=dest_repo)
    _run(["git", "add", "."], cwd=dest_repo)
    _run(["git", "commit", "-m", "starter"], cwd=dest_repo)
    starter_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=dest_repo, text=True).strip()

    metadata = {
        "starter_repo": str(starter_repo),
        "dest_repo": str(dest_repo),
        "starter_commit": starter_commit,
        "tree_hash": tree_hash(dest_repo),
        "git_initialized": True,
    }
    metadata_out.parent.mkdir(parents=True, exist_ok=True)
    metadata_out.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a clean git-initialized run workspace from a starter repo.")
    parser.add_argument("--starter-repo", required=True)
    parser.add_argument("--dest-repo", required=True)
    parser.add_argument("--metadata-out", required=True)
    args = parser.parse_args(argv)
    metadata = prepare_run_workspace(Path(args.starter_repo), Path(args.dest_repo), Path(args.metadata_out))
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
