from __future__ import annotations

import argparse
import fnmatch
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

PROTECTED_DIRS = {
    ".git",
    "src",
    "tests",
    "fixtures",
    "scripts",
    "benchmark_harness",
}
ARTIFACT_SUFFIXES = {".md", ".txt", ".rst"}
RESUME_OUTPUT_SENTINELS = {
    "FRESH_SESSION_REVIEW.md",
    ".benchmark_resume_started",
}


@dataclass
class StripResult:
    removed: list[str]
    kept_required_outputs: list[str]
    skipped: list[dict[str, str]]
    ambiguous_not_removed: list[dict[str, str]]
    dry_run: bool


def _rel(path: Path, repo: Path) -> str:
    return path.relative_to(repo).as_posix()


def _load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("required_outputs", [])
    data.setdefault("workflow_artifact_patterns", [])
    data.setdefault("strip_timing", {})
    return data


def default_strip_metadata_path(repo: Path) -> Path:
    """Default to an external metadata file, never a file inside the repo."""
    return repo.parent / "metadata" / "stripped_artifacts_manifest.json"


def _is_under_protected_dir(path: Path, repo: Path) -> bool:
    parts = path.relative_to(repo).parts
    return bool(parts) and parts[0] in PROTECTED_DIRS


def _is_required_output(rel_path: str, required_outputs: set[str]) -> bool:
    return rel_path in required_outputs


def _is_artifact_like(path: Path) -> bool:
    return path.suffix.lower() in ARTIFACT_SUFFIXES


def _matched_candidates(repo: Path, patterns: Iterable[str]) -> set[Path]:
    candidates: set[Path] = set()
    all_files = [p for p in repo.rglob("*") if p.is_file()]
    for pattern in patterns:
        for path in all_files:
            rel_path = _rel(path, repo)
            if fnmatch.fnmatch(rel_path, pattern):
                candidates.add(path)
    return candidates


def _check_strip_timing(repo: Path, manifest: dict[str, Any]) -> None:
    timing = manifest.get("strip_timing") or {}
    if not timing.get("forbidden_after_resume_outputs"):
        return
    present = [name for name in RESUME_OUTPUT_SENTINELS if (repo / name).exists()]
    if present:
        raise RuntimeError(
            "Refusing to strip artifacts after resume outputs exist: " + ", ".join(present)
        )


def strip_workflow_artifacts(
    repo: str | Path,
    manifest_path: str | Path,
    out_path: str | Path | None = None,
    dry_run: bool = False,
) -> StripResult:
    repo = Path(repo).resolve()
    manifest_path = Path(manifest_path).resolve()
    out_path = Path(out_path).resolve() if out_path else default_strip_metadata_path(repo)
    try:
        out_path.relative_to(repo)
    except ValueError:
        pass
    else:
        raise ValueError("stripped artifacts manifest must be outside the agent-visible repo")

    manifest = _load_manifest(manifest_path)
    _check_strip_timing(repo, manifest)

    required_outputs = {str(path).strip("/") for path in manifest.get("required_outputs", [])}
    patterns = manifest.get("workflow_artifact_patterns", [])

    result = StripResult(
        removed=[],
        kept_required_outputs=[],
        skipped=[],
        ambiguous_not_removed=[],
        dry_run=dry_run,
    )

    candidates = _matched_candidates(repo, patterns)
    for path in sorted(candidates, key=lambda p: _rel(p, repo)):
        rel_path = _rel(path, repo)
        if _is_required_output(rel_path, required_outputs):
            result.kept_required_outputs.append(rel_path)
            continue
        if _is_under_protected_dir(path, repo):
            result.skipped.append({"path": rel_path, "reason": "protected_directory"})
            continue
        if not _is_artifact_like(path):
            result.skipped.append({"path": rel_path, "reason": "not_artifact_suffix"})
            continue
        result.removed.append(rel_path)
        if not dry_run:
            path.unlink()

    for required in sorted(required_outputs):
        if (repo / required).exists() and required not in result.kept_required_outputs:
            result.kept_required_outputs.append(required)

    remaining_markdown = [p for p in repo.rglob("*.md") if p.is_file()]
    matched_rels = {_rel(p, repo) for p in candidates}
    for path in sorted(remaining_markdown, key=lambda p: _rel(p, repo)):
        rel_path = _rel(path, repo)
        if rel_path in required_outputs:
            continue
        if rel_path in matched_rels:
            continue
        if _is_under_protected_dir(path, repo):
            continue
        result.ambiguous_not_removed.append(
            {"path": rel_path, "reason": "ambiguous_not_removed"}
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remove workflow artifacts for artifact-stripped resume workspaces.")
    parser.add_argument("--repo", required=True, help="Repository root to strip")
    parser.add_argument("--manifest", required=True, help="task_output_manifest.yml")
    parser.add_argument("--out", default=None, help="External stripped_artifacts_manifest.json path")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = strip_workflow_artifacts(args.repo, args.manifest, args.out, args.dry_run)
    except RuntimeError as exc:
        print(str(exc))
        return 2
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
