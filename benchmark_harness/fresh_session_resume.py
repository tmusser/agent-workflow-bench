from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from benchmark_harness.telemetry import KNOWN_ARTIFACTS

SCHEMA_VERSION = 1
DEFAULT_CONDITIONS = ("full", "stripped")
REVIEW_FILES = ("FRESH_SESSION_REVIEW.md", "BUGFIX_REVIEW.md")


@dataclass(frozen=True)
class ResumeCondition:
    condition: str
    repo: str
    out_dir: str
    workspace_exists: bool
    attempted: bool
    verify_exit_code: int | None
    hidden_evaluator_exit_code: int | None
    passed: bool | None
    diff_bytes: int | None
    git_status_lines: int | None
    review_files: list[str]
    workflow_artifacts_present: list[str]
    metadata: dict[str, object] | None


@dataclass(frozen=True)
class FreshSessionResumeSummary:
    schema_version: int
    run_id: str
    conditions: list[ResumeCondition]
    comparison: dict[str, object]


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _read_int(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _line_count(path: Path) -> int | None:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
    except OSError:
        return None


def _file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def condition_repo(root: Path, run_id: str, condition: str) -> Path:
    if condition not in DEFAULT_CONDITIONS:
        raise ValueError(f"unknown resume condition: {condition}")
    return root / "benchmark-data" / "resume-workspaces" / run_id / condition / "repo"


def condition_out_dir(root: Path, run_id: str, condition: str) -> Path:
    if condition not in DEFAULT_CONDITIONS:
        raise ValueError(f"unknown resume condition: {condition}")
    return root / "benchmark-data" / "resume-runs" / f"{run_id}_{condition}"


def condition_metadata_path(root: Path, run_id: str, condition: str) -> Path:
    return root / "benchmark-data" / "resume-workspaces" / run_id / condition / "metadata" / "resume_workspace_manifest.json"


def workflow_artifacts(repo: Path) -> list[str]:
    if not repo.exists():
        return []
    present = [name for name in KNOWN_ARTIFACTS if (repo / name).is_file()]
    return sorted(present)


def review_files(out_dir: Path) -> list[str]:
    return sorted(name for name in REVIEW_FILES if (out_dir / name).is_file())


def summarize_condition(root: Path, run_id: str, condition: str) -> ResumeCondition:
    repo = condition_repo(root, run_id, condition)
    out_dir = condition_out_dir(root, run_id, condition)
    workspace_exists = (repo / ".git").is_dir() or repo.is_dir()
    attempted = any(
        (out_dir / name).exists()
        for name in (
            "verification.txt",
            "hidden_evaluator.txt",
            "verification_exit_code.txt",
            "hidden_evaluator_exit_code.txt",
            "run_metrics.json",
        )
    )
    verify_exit_code = _read_int(out_dir / "verification_exit_code.txt")
    hidden_exit_code = _read_int(out_dir / "hidden_evaluator_exit_code.txt")
    passed = None
    if verify_exit_code is not None and hidden_exit_code is not None:
        passed = verify_exit_code == 0 and hidden_exit_code == 0
    return ResumeCondition(
        condition=condition,
        repo=_rel(repo, root),
        out_dir=_rel(out_dir, root),
        workspace_exists=workspace_exists,
        attempted=attempted,
        verify_exit_code=verify_exit_code,
        hidden_evaluator_exit_code=hidden_exit_code,
        passed=passed,
        diff_bytes=_file_size(out_dir / "diff.patch"),
        git_status_lines=_line_count(out_dir / "git_status.txt"),
        review_files=review_files(out_dir),
        workflow_artifacts_present=workflow_artifacts(repo),
        metadata=_read_json(condition_metadata_path(root, run_id, condition)),
    )


def compare_conditions(conditions: Sequence[ResumeCondition]) -> dict[str, object]:
    by_name = {condition.condition: condition for condition in conditions}
    full = by_name.get("full")
    stripped = by_name.get("stripped")
    if full is None or stripped is None:
        return {"status": "incomplete", "reason": "missing_condition"}
    if full.passed is None or stripped.passed is None:
        return {"status": "incomplete", "reason": "missing_exit_codes"}
    if full.passed and not stripped.passed:
        winner = "full"
    elif stripped.passed and not full.passed:
        winner = "stripped"
    else:
        winner = "tie"
    return {
        "status": "complete",
        "winner": winner,
        "full_passed": full.passed,
        "stripped_passed": stripped.passed,
        "artifact_advantage_observed": winner == "full",
    }


def summarize_resume_run(root: str | Path, run_id: str, conditions: Iterable[str] = DEFAULT_CONDITIONS) -> FreshSessionResumeSummary:
    root_path = Path(root).resolve()
    summarized = [summarize_condition(root_path, run_id, condition) for condition in conditions]
    return FreshSessionResumeSummary(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        conditions=summarized,
        comparison={"full_vs_stripped": compare_conditions(summarized)},
    )


def write_summary(summary: FreshSessionResumeSummary, out: str | Path) -> Path:
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(asdict(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path


def default_summary_path(root: Path, run_id: str) -> Path:
    return root / "benchmark-data" / "runs" / run_id / "fresh_session_resume_summary.json"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_capture(command: list[str], *, cwd: Path, out_path: Path) -> int:
    proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    output = ""
    if proc.stdout:
        output += proc.stdout
    if proc.stderr:
        if output and not output.endswith("\n"):
            output += "\n"
        output += proc.stderr
    _write_text(out_path, output)
    return proc.returncode


def _git_capture(repo: Path, args: list[str], out_path: Path) -> None:
    try:
        proc = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=False)
    except OSError as exc:
        _write_text(out_path, f"git unavailable: {exc}\n")
        return
    _write_text(out_path, proc.stdout + proc.stderr)


def evaluate_condition(root: str | Path, run_id: str, condition: str, evaluator_module: str) -> ResumeCondition:
    root_path = Path(root).resolve()
    repo = condition_repo(root_path, run_id, condition)
    out_dir = condition_out_dir(root_path, run_id, condition)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not repo.is_dir():
        raise FileNotFoundError(f"resume workspace not found: {repo}")

    verify_exit = _run_capture(["./VERIFY.sh"], cwd=repo, out_path=out_dir / "verification.txt")
    _write_text(out_dir / "verification_exit_code.txt", f"{verify_exit}\n")

    hidden_exit = _run_capture([sys.executable, "-m", evaluator_module, "--repo", str(repo)], cwd=root_path, out_path=out_dir / "hidden_evaluator.txt")
    _write_text(out_dir / "hidden_evaluator_exit_code.txt", f"{hidden_exit}\n")

    _git_capture(repo, ["status", "--short"], out_dir / "git_status.txt")
    _git_capture(repo, ["diff", "--stat", "HEAD"], out_dir / "diff_stat.txt")
    _git_capture(repo, ["diff", "HEAD"], out_dir / "diff.patch")

    for name in REVIEW_FILES:
        src = repo / name
        if src.is_file():
            _write_text(out_dir / name, src.read_text(encoding="utf-8", errors="replace"))

    return summarize_condition(root_path, run_id, condition)


def evaluate_resume_run(root: str | Path, run_id: str, evaluator_module: str, conditions: Iterable[str] = DEFAULT_CONDITIONS) -> FreshSessionResumeSummary:
    root_path = Path(root).resolve()
    for condition in conditions:
        evaluate_condition(root_path, run_id, condition, evaluator_module)
    return summarize_resume_run(root_path, run_id, conditions)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate or summarize fresh-session resume conditions.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser("summarize", help="Summarize existing fresh-session resume outputs.")
    summary_parser.add_argument("--root", default=".")
    summary_parser.add_argument("--run-id", required=True)
    summary_parser.add_argument("--out")
    summary_parser.add_argument("--conditions", nargs="+", default=list(DEFAULT_CONDITIONS), choices=list(DEFAULT_CONDITIONS))

    eval_parser = subparsers.add_parser("evaluate", help="Run local verification/evaluator checks for resume workspaces, then summarize.")
    eval_parser.add_argument("--root", default=".")
    eval_parser.add_argument("--run-id", required=True)
    eval_parser.add_argument("--resume-evaluator-module", required=True)
    eval_parser.add_argument("--out")
    eval_parser.add_argument("--conditions", nargs="+", default=list(DEFAULT_CONDITIONS), choices=list(DEFAULT_CONDITIONS))

    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    out = Path(args.out) if args.out else default_summary_path(root, args.run_id)
    if args.command == "summarize":
        summary = summarize_resume_run(root, args.run_id, args.conditions)
    elif args.command == "evaluate":
        summary = evaluate_resume_run(root, args.run_id, args.resume_evaluator_module, args.conditions)
    else:  # pragma: no cover - argparse protects this.
        raise AssertionError(f"unhandled command: {args.command}")
    write_summary(summary, out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
