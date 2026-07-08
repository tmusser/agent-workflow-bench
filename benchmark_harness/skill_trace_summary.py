from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

SCHEMA_VERSION = 1
PHASES = ("initial", "full", "stripped")
TRACE_FILENAME = "SKILL_TRACE.jsonl"
ALLOWED_EVENT_TYPES = (
    "skill_available",
    "skill_considered",
    "skill_invoked",
    "skill_skipped",
)
ARTIFACT_ALIGNMENT = {
    "verify-contract": "VERIFY.md",
    "handoff": "HANDOFF.md",
}


@dataclass(frozen=True)
class InvalidTraceRow:
    line_number: int
    error: str
    raw: str


@dataclass(frozen=True)
class ArtifactAlignmentSummary:
    skill_name: str
    artifact_path: str
    artifact_present: bool
    declared_invoked: bool
    aligned: bool


@dataclass(frozen=True)
class SkillTraceSummary:
    schema_version: int
    run_id: str | None
    phase: str | None
    repo: str
    trace_present: bool
    trace_path: str
    trace_bytes: int
    claim_boundary: str
    evidence_level: str
    event_counts: dict[str, int]
    declared_available_skills: list[str]
    declared_considered_skills: list[str]
    declared_invoked_skills: list[str]
    declared_skipped_skills: list[str]
    declared_events_by_turn: dict[str, dict[str, list[str]]]
    invalid_rows: list[InvalidTraceRow]
    artifact_alignment: list[ArtifactAlignmentSummary]
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


def _parse_trace_row(raw_line: str, *, line_number: int) -> tuple[dict[str, object] | None, InvalidTraceRow | None]:
    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError as exc:
        return None, InvalidTraceRow(line_number=line_number, error=f"malformed_json: {exc.msg}", raw=raw_line)
    if not isinstance(payload, dict):
        return None, InvalidTraceRow(line_number=line_number, error="row_must_be_json_object", raw=raw_line)

    event_type = payload.get("event_type")
    skill_name = payload.get("skill_name")
    if not isinstance(event_type, str) or not event_type:
        return None, InvalidTraceRow(line_number=line_number, error="missing_event_type", raw=raw_line)
    if event_type not in ALLOWED_EVENT_TYPES:
        return None, InvalidTraceRow(line_number=line_number, error=f"unknown_event_type: {event_type}", raw=raw_line)
    if not isinstance(skill_name, str) or not skill_name.strip():
        return None, InvalidTraceRow(line_number=line_number, error="missing_skill_name", raw=raw_line)

    parsed: dict[str, object] = {"event_type": event_type, "skill_name": skill_name.strip()}
    turn_index = payload.get("turn_index")
    if isinstance(turn_index, int) and not isinstance(turn_index, bool):
        parsed["turn_index"] = turn_index
    elif isinstance(turn_index, float) and turn_index.is_integer():
        parsed["turn_index"] = int(turn_index)
    elif isinstance(turn_index, str):
        try:
            parsed["turn_index"] = int(turn_index)
        except ValueError:
            pass
    return parsed, None


def _collect_trace(
    repo: Path,
) -> tuple[bool, int, dict[str, int], dict[str, set[str]], dict[str, dict[str, set[str]]], list[InvalidTraceRow]]:
    trace_path = repo / TRACE_FILENAME
    event_counts = {event_type: 0 for event_type in ALLOWED_EVENT_TYPES}
    skills_by_event = {event_type: set() for event_type in ALLOWED_EVENT_TYPES}
    events_by_turn: dict[str, dict[str, set[str]]] = {}
    invalid_rows: list[InvalidTraceRow] = []

    if not trace_path.is_file():
        return False, 0, event_counts, skills_by_event, events_by_turn, invalid_rows

    for index, raw_line in enumerate(trace_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            invalid_rows.append(InvalidTraceRow(line_number=index, error="blank_line", raw=raw_line))
            continue
        parsed, issue = _parse_trace_row(line, line_number=index)
        if issue is not None:
            invalid_rows.append(issue)
            continue
        assert parsed is not None
        event_type = parsed["event_type"]
        skill_name = str(parsed["skill_name"])
        event_counts[event_type] += 1
        skills_by_event[event_type].add(skill_name)
        turn_index = parsed.get("turn_index")
        if isinstance(turn_index, int) and not isinstance(turn_index, bool):
            turn_key = str(turn_index)
            turn_event_map = events_by_turn.setdefault(turn_key, {event: set() for event in ALLOWED_EVENT_TYPES})
            turn_event_map[event_type].add(skill_name)

    return True, _file_size(trace_path), event_counts, skills_by_event, events_by_turn, invalid_rows


def _normalize_turn_events(events_by_turn: dict[str, dict[str, set[str]]]) -> dict[str, dict[str, list[str]]]:
    def _turn_sort_key(item: tuple[str, dict[str, set[str]]]) -> tuple[int, str]:
        turn_key = item[0]
        try:
            return int(turn_key), turn_key
        except ValueError:
            return 10**9, turn_key

    normalized: dict[str, dict[str, list[str]]] = {}
    for turn_key, event_map in sorted(events_by_turn.items(), key=_turn_sort_key):
        normalized[turn_key] = {
            event_type: sorted(skills)
            for event_type, skills in sorted(event_map.items())
            if skills
        }
    return normalized


def _artifact_alignment(repo: Path, declared_invoked: set[str]) -> list[ArtifactAlignmentSummary]:
    rows: list[ArtifactAlignmentSummary] = []
    for skill_name, artifact_path in sorted(ARTIFACT_ALIGNMENT.items()):
        artifact_present = (repo / artifact_path).is_file()
        declared = skill_name in declared_invoked
        if artifact_present or declared:
            rows.append(
                ArtifactAlignmentSummary(
                    skill_name=skill_name,
                    artifact_path=artifact_path,
                    artifact_present=artifact_present,
                    declared_invoked=declared,
                    aligned=artifact_present and declared,
                )
            )
    return rows


def _evidence_level(trace_present: bool, event_counts: dict[str, int]) -> str:
    declared_events = sum(event_counts[event_type] for event_type in ("skill_considered", "skill_invoked", "skill_skipped"))
    if declared_events > 0:
        return "agent_declared"
    if trace_present and event_counts["skill_available"] > 0:
        return "availability_only"
    return "availability_only"


def summarize_repo(repo: str | Path, *, run_id: str | None = None, phase: str | None = None) -> SkillTraceSummary:
    repo_path = Path(repo).resolve()
    trace_present, trace_bytes, event_counts, skills_by_event, events_by_turn, invalid_rows = _collect_trace(repo_path)
    declared_invoked = set(skills_by_event["skill_invoked"])
    artifact_alignment = _artifact_alignment(repo_path, declared_invoked)
    evidence_level = _evidence_level(trace_present, event_counts)
    valid_rows = sum(event_counts.values())
    normalized_turn_events = _normalize_turn_events(events_by_turn)
    return SkillTraceSummary(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        phase=phase,
        repo=_rel(repo_path, Path.cwd()),
        trace_present=trace_present,
        trace_path=TRACE_FILENAME,
        trace_bytes=trace_bytes,
        claim_boundary="agent_declared_trace_not_runtime_hook_invocation",
        evidence_level=evidence_level,
        event_counts=event_counts,
        declared_available_skills=sorted(skills_by_event["skill_available"]),
        declared_considered_skills=sorted(skills_by_event["skill_considered"]),
        declared_invoked_skills=sorted(declared_invoked),
        declared_skipped_skills=sorted(skills_by_event["skill_skipped"]),
        declared_events_by_turn=normalized_turn_events,
        invalid_rows=invalid_rows,
        artifact_alignment=artifact_alignment,
        summary={
            "valid_rows": valid_rows,
            "invalid_rows": len(invalid_rows),
            "trace_present": trace_present,
            "trace_bytes": trace_bytes,
            "declared_invoked_skills_count": len(declared_invoked),
            "declared_skipped_skills_count": len(skills_by_event["skill_skipped"]),
            "declared_turn_indices": [int(turn) for turn in normalized_turn_events.keys()] if normalized_turn_events else [],
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
        return root / "benchmark-data" / "runs" / run_id / "skill_trace_summary.json"
    if phase in {"full", "stripped"}:
        return root / "benchmark-data" / "resume-runs" / f"{run_id}_{phase}" / "skill_trace_summary.json"
    raise ValueError(f"unknown phase: {phase}")


def write_summary(summary: SkillTraceSummary, out: str | Path) -> Path:
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(asdict(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path


def summarize_run(root: str | Path, run_id: str, *, phase: str = "initial") -> SkillTraceSummary:
    root_path = Path(root).resolve()
    return summarize_repo(repo_for_phase(root_path, run_id, phase), run_id=run_id, phase=phase)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize agent-declared skill trace evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    repo_parser = subparsers.add_parser("summarize", help="Summarize SKILL_TRACE.jsonl in one repository.")
    repo_parser.add_argument("--repo", required=True)
    repo_parser.add_argument("--run-id")
    repo_parser.add_argument("--phase")
    repo_parser.add_argument("--out", required=True)

    run_parser = subparsers.add_parser("summarize-run", help="Summarize SKILL_TRACE.jsonl for one benchmark run phase.")
    run_parser.add_argument("--root", default=".")
    run_parser.add_argument("--run-id", required=True)
    run_parser.add_argument("--phase", required=True, choices=PHASES)
    run_parser.add_argument("--out")

    args = parser.parse_args(argv)
    if args.command == "summarize":
        out_path = write_summary(summarize_repo(args.repo, run_id=args.run_id, phase=args.phase), args.out)
        print(out_path)
        return 0
    if args.command == "summarize-run":
        root = Path(args.root).resolve()
        out = Path(args.out) if args.out else default_out_for_phase(root, args.run_id, args.phase)
        out_path = write_summary(summarize_run(root, args.run_id, phase=args.phase), out)
        print(out_path)
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
