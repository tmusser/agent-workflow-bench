from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping

from benchmark_harness.telemetry import KNOWN_ARTIFACTS

SCHEMA_VERSION = 1
DEFAULT_EXPECTED_ARTIFACTS = ("VERIFY.md", "HANDOFF.md")
PHASES = ("initial", "full", "stripped")

CHECK_PATTERNS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "VERIFY.md": (
        ("has_verification_command", (r"\bpython\b", r"\bpytest\b", r"\bVERIFY\.sh\b", r"\bnpm\s+test\b", r"\bmake\s+test\b")),
        ("has_result_status", (r"\bpass(?:ed)?\b", r"\bfail(?:ed)?\b", r"\bgreen\b", r"\bred\b", r"\bexit\s*code\b", r"\b0\s+failed\b")),
        ("has_scope_or_evidence", (r"\bevidence\b", r"\bverified\b", r"\bcoverage\b", r"\bregression\b", r"\bhidden\b")),
    ),
    "HANDOFF.md": (
        ("has_next_step", (r"\bnext\b", r"\bresume\b", r"\bcontinue\b", r"\bfollow[- ]?up\b")),
        ("has_risk_or_uncertainty", (r"\brisk\b", r"\buncertain", r"\bblocker\b", r"\bwarning\b", r"\btrap\b", r"\bmissing\b")),
        ("has_verification_state", (r"\bverify\b", r"\btest\b", r"\bpass(?:ed)?\b", r"\bfail(?:ed)?\b", r"\bgreen\b", r"\bred\b")),
    ),
    "BUGS.md": (
        ("has_bug_or_root_cause", (r"\bbug\b", r"\broot cause\b", r"\bcause\b", r"\bfailure\b")),
        ("has_fix_or_status", (r"\bfix\b", r"\bfixed\b", r"\bstatus\b", r"\bremaining\b")),
    ),
    "PLAN.md": (
        ("has_steps", (r"\bstep\b", r"\bplan\b", r"\b1\.\b", r"\b- \[ \]\b")),
        ("has_verification", (r"\bverify\b", r"\btest\b", r"\bcheck\b")),
    ),
    "SPEC.md": (
        ("has_goal_or_contract", (r"\bgoal\b", r"\bcontract\b", r"\bscope\b", r"\brequirement\b")),
        ("has_acceptance_or_verify", (r"\bacceptance\b", r"\bverify\b", r"\btest\b", r"\bpass\b")),
    ),
    "FRESH_SESSION_REVIEW.md": (
        ("has_files_read", (r"\bfiles? read\b", r"\bread first\b", r"\binspected\b")),
        ("has_resume_assessment", (r"\bresume\b", r"\bdurable context\b", r"\brediscovery\b", r"\bprior artifacts\b")),
        ("has_verification", (r"\bverify\b", r"\btest\b", r"\bcommand\b", r"\bresult\b")),
    ),
    "BUGFIX_REVIEW.md": (
        ("has_root_cause", (r"\broot cause\b", r"\bcause\b", r"\bbug\b")),
        ("has_regression_evidence", (r"\bregression\b", r"\btest\b", r"\bVERIFY\.sh\b", r"\bpytest\b")),
    ),
}

GENERIC_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("has_heading", (r"^#", r"\n#")),
    ("has_actionable_words", (r"\bverify\b", r"\btest\b", r"\bnext\b", r"\brisk\b", r"\bstatus\b", r"\bchanged\b")),
)


@dataclass(frozen=True)
class ArtifactCheck:
    path: str
    expected: bool
    exists: bool
    bytes: int
    lines: int
    checks: dict[str, bool]
    checks_passed: int
    checks_total: int
    usable: bool


@dataclass(frozen=True)
class ArtifactUsabilitySummary:
    schema_version: int
    run_id: str | None
    phase: str | None
    repo: str
    expected_artifacts: list[str]
    artifacts: dict[str, ArtifactCheck]
    score: dict[str, object]


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _artifact_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def _matches_any(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) for pattern in patterns)


def checks_for_artifact(name: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return CHECK_PATTERNS.get(name, GENERIC_CHECKS)


def evaluate_artifact(repo: Path, name: str, *, expected: bool) -> ArtifactCheck:
    path = repo / name
    if not path.is_file():
        checks = {check_name: False for check_name, _ in checks_for_artifact(name)}
        return ArtifactCheck(
            path=name,
            expected=expected,
            exists=False,
            bytes=0,
            lines=0,
            checks=checks,
            checks_passed=0,
            checks_total=len(checks),
            usable=False,
        )

    text = _read_text(path)
    byte_count = path.stat().st_size
    line_count = _artifact_lines(text)
    checks = {check_name: _matches_any(text, patterns) for check_name, patterns in checks_for_artifact(name)}
    checks_passed = sum(1 for passed in checks.values() if passed)
    checks_total = len(checks)
    usable = byte_count > 0 and line_count > 0 and checks_passed == checks_total
    return ArtifactCheck(
        path=name,
        expected=expected,
        exists=True,
        bytes=byte_count,
        lines=line_count,
        checks=checks,
        checks_passed=checks_passed,
        checks_total=checks_total,
        usable=usable,
    )


def discover_artifacts(repo: Path) -> list[str]:
    return sorted(name for name in KNOWN_ARTIFACTS if (repo / name).is_file())


def summarize_repo(
    repo: str | Path,
    *,
    run_id: str | None = None,
    phase: str | None = None,
    expected_artifacts: Iterable[str] = DEFAULT_EXPECTED_ARTIFACTS,
) -> ArtifactUsabilitySummary:
    repo_path = Path(repo).resolve()
    expected = [name for name in dict.fromkeys(expected_artifacts)]
    names = sorted(set(expected) | set(discover_artifacts(repo_path)))
    artifacts = {name: evaluate_artifact(repo_path, name, expected=name in expected) for name in names}
    checks_passed = sum(artifact.checks_passed for artifact in artifacts.values())
    checks_total = sum(artifact.checks_total for artifact in artifacts.values())
    expected_present = sum(1 for name in expected if artifacts.get(name) and artifacts[name].exists)
    expected_usable = sum(1 for name in expected if artifacts.get(name) and artifacts[name].usable)
    score = {
        "artifacts_checked": len(artifacts),
        "expected_present": expected_present,
        "expected_total": len(expected),
        "expected_usable": expected_usable,
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "usable": bool(expected) and expected_usable == len(expected),
    }
    return ArtifactUsabilitySummary(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        phase=phase,
        repo=_rel(repo_path, Path.cwd()),
        expected_artifacts=expected,
        artifacts=artifacts,
        score=score,
    )


def repo_for_phase(root: Path, run_id: str, phase: str) -> Path:
    if phase == "initial":
        return root / "benchmark-data" / "workspaces" / run_id / "repo"
    if phase == "full":
        return root / "benchmark-data" / "resume-workspaces" / run_id / "full" / "repo"
    if phase == "stripped":
        return root / "benchmark-data" / "resume-workspaces" / run_id / "stripped" / "repo"
    raise ValueError(f"unknown phase: {phase}")


def default_out_for_phase(root: Path, run_id: str, phase: str) -> Path:
    if phase == "initial":
        return root / "benchmark-data" / "runs" / run_id / "artifact_usability_summary.json"
    if phase in {"full", "stripped"}:
        return root / "benchmark-data" / "resume-runs" / f"{run_id}_{phase}" / "artifact_usability_summary.json"
    raise ValueError(f"unknown phase: {phase}")


def write_summary(summary: ArtifactUsabilitySummary, out: str | Path) -> Path:
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(asdict(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path


def _parse_expected(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return DEFAULT_EXPECTED_ARTIFACTS
    return tuple(value for item in values for value in item.split(",") if value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize workflow artifact usability with deterministic checks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    repo_parser = subparsers.add_parser("summarize", help="Summarize artifacts in one repository.")
    repo_parser.add_argument("--repo", required=True)
    repo_parser.add_argument("--run-id")
    repo_parser.add_argument("--phase")
    repo_parser.add_argument("--out", required=True)
    repo_parser.add_argument("--expected", action="append", help="Expected artifact name or comma-separated names. Defaults to VERIFY.md,HANDOFF.md.")

    run_parser = subparsers.add_parser("summarize-run", help="Summarize a benchmark run workspace by phase.")
    run_parser.add_argument("--root", default=".")
    run_parser.add_argument("--run-id", required=True)
    run_parser.add_argument("--phase", choices=PHASES, default="initial")
    run_parser.add_argument("--out")
    run_parser.add_argument("--expected", action="append", help="Expected artifact name or comma-separated names. Defaults to VERIFY.md,HANDOFF.md.")

    args = parser.parse_args(argv)
    expected = _parse_expected(args.expected)
    if args.command == "summarize":
        summary = summarize_repo(args.repo, run_id=args.run_id, phase=args.phase, expected_artifacts=expected)
        out = Path(args.out)
    elif args.command == "summarize-run":
        root = Path(args.root).resolve()
        summary = summarize_repo(repo_for_phase(root, args.run_id, args.phase), run_id=args.run_id, phase=args.phase, expected_artifacts=expected)
        out = Path(args.out) if args.out else default_out_for_phase(root, args.run_id, args.phase)
    else:  # pragma: no cover - argparse protects this.
        raise AssertionError(f"unhandled command: {args.command}")
    write_summary(summary, out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
