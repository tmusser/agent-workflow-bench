from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from benchmark_harness.validate_skill_runtime_proof import validate as validate_skill_runtime_proof

SCHEMA_VERSION = 1
PHASES = ("initial", "full", "stripped")
SKILL_RUNTIME_PROOF = "SKILL_RUNTIME_PROOF.md"

SKILL_EVIDENCE: dict[str, tuple[str, ...]] = {
    "mini-spec": ("SPEC.md",),
    "thin-plan": ("PLAN.md", "TODO.md"),
    "verify-contract": ("VERIFY.md",),
    "handoff": ("HANDOFF.md",),
    "bug-capture": ("BUGS.md",),
    "diagnose-loop": ("BUGFIX_REVIEW.md", "FRESH_SESSION_REVIEW.md"),
    "grill-with-docs-lite": ("DATA_AUDIT.md", "TRUST_AUDIT.md"),
}


@dataclass(frozen=True)
class SkillRuntimeProofSummary:
    exists: bool
    valid: bool | None
    path: str
    bytes: int
    issues: list[str]


@dataclass(frozen=True)
class SkillEvidenceSummary:
    present: bool
    evidence: list[str]
    evidence_count: int


@dataclass(frozen=True)
class SkillRoutingSummary:
    schema_version: int
    run_id: str | None
    phase: str | None
    arm_slug: str | None
    repo: str
    claim_boundary: str
    skill_runtime_proof: SkillRuntimeProofSummary
    inferred_skills: dict[str, SkillEvidenceSummary]
    summary: dict[str, object]


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def summarize_skill_runtime_proof(repo: Path) -> SkillRuntimeProofSummary:
    proof = repo / SKILL_RUNTIME_PROOF
    if not proof.is_file():
        return SkillRuntimeProofSummary(
            exists=False,
            valid=None,
            path=SKILL_RUNTIME_PROOF,
            bytes=0,
            issues=["missing"],
        )
    try:
        issues = validate_skill_runtime_proof(proof)
    except OSError as exc:
        issues = [f"unreadable: {exc.__class__.__name__}: {exc}"]
    return SkillRuntimeProofSummary(
        exists=True,
        valid=not issues,
        path=SKILL_RUNTIME_PROOF,
        bytes=_file_size(proof),
        issues=issues,
    )


def infer_skills(repo: Path, skill_evidence: dict[str, tuple[str, ...]] = SKILL_EVIDENCE) -> dict[str, SkillEvidenceSummary]:
    inferred: dict[str, SkillEvidenceSummary] = {}
    for skill, artifacts in skill_evidence.items():
        evidence = sorted(name for name in artifacts if (repo / name).is_file())
        inferred[skill] = SkillEvidenceSummary(
            present=bool(evidence),
            evidence=evidence,
            evidence_count=len(evidence),
        )
    return inferred


def evidence_level(proof: SkillRuntimeProofSummary, inferred: dict[str, SkillEvidenceSummary]) -> str:
    inferred_count = sum(1 for item in inferred.values() if item.present)
    if proof.valid is True and inferred_count > 0:
        return "runtime_proven"
    if inferred_count > 0:
        return "present"
    if proof.exists:
        return "proof_only"
    return "absent"


def summarize_repo(
    repo: str | Path,
    *,
    run_id: str | None = None,
    phase: str | None = None,
    arm_slug: str | None = None,
) -> SkillRoutingSummary:
    repo_path = Path(repo).resolve()
    proof = summarize_skill_runtime_proof(repo_path)
    inferred = infer_skills(repo_path)
    skills_inferred = sorted(skill for skill, item in inferred.items() if item.present)
    evidence_files = sorted({name for item in inferred.values() for name in item.evidence})
    return SkillRoutingSummary(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        phase=phase,
        arm_slug=arm_slug,
        repo=_rel(repo_path, Path.cwd()),
        claim_boundary="inferred_from_artifacts_not_runtime_invocation_trace",
        skill_runtime_proof=proof,
        inferred_skills=inferred,
        summary={
            "skills_inferred": len(skills_inferred),
            "skills": skills_inferred,
            "evidence_files": evidence_files,
            "evidence_files_count": len(evidence_files),
            "evidence_level": evidence_level(proof, inferred),
            "runtime_proof_valid": proof.valid,
        },
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
        return root / "benchmark-data" / "runs" / run_id / "skill_routing_summary.json"
    if phase in {"full", "stripped"}:
        return root / "benchmark-data" / "resume-runs" / f"{run_id}_{phase}" / "skill_routing_summary.json"
    raise ValueError(f"unknown phase: {phase}")


def write_summary(summary: SkillRoutingSummary, out: str | Path) -> Path:
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(asdict(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path


def summarize_run(
    root: str | Path,
    run_id: str,
    *,
    phase: str = "initial",
    arm_slug: str | None = None,
) -> SkillRoutingSummary:
    root_path = Path(root).resolve()
    return summarize_repo(repo_for_phase(root_path, run_id, phase), run_id=run_id, phase=phase, arm_slug=arm_slug)


def _parse_phases(values: Iterable[str] | None) -> list[str]:
    phases = list(values or ["initial"])
    for phase in phases:
        if phase not in PHASES:
            raise ValueError(f"unknown phase: {phase}")
    return phases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize inferred skill-routing evidence from durable artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    repo_parser = subparsers.add_parser("summarize", help="Summarize inferred skill evidence in one repository.")
    repo_parser.add_argument("--repo", required=True)
    repo_parser.add_argument("--run-id")
    repo_parser.add_argument("--phase")
    repo_parser.add_argument("--arm-slug")
    repo_parser.add_argument("--out", required=True)

    run_parser = subparsers.add_parser("summarize-run", help="Summarize inferred skill evidence using benchmark run layout.")
    run_parser.add_argument("--root", default=".")
    run_parser.add_argument("--run-id", required=True)
    run_parser.add_argument("--phase", action="append", choices=PHASES, help="Phase to summarize. Repeat for multiple phases. Defaults to initial.")
    run_parser.add_argument("--arm-slug")
    run_parser.add_argument("--out", help="Output path; only valid when summarizing one phase.")

    args = parser.parse_args(argv)
    if args.command == "summarize":
        summary = summarize_repo(args.repo, run_id=args.run_id, phase=args.phase, arm_slug=args.arm_slug)
        write_summary(summary, args.out)
        print(args.out)
        return 0

    if args.command == "summarize-run":
        root = Path(args.root).resolve()
        phases = _parse_phases(args.phase)
        if args.out and len(phases) != 1:
            parser.error("--out can only be used with exactly one --phase")
        for phase in phases:
            summary = summarize_run(root, args.run_id, phase=phase, arm_slug=args.arm_slug)
            out = Path(args.out) if args.out else default_out_for_phase(root, args.run_id, phase)
            write_summary(summary, out)
            print(out)
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
