from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from benchmark_harness.evidence_status import infer_command_exit
from benchmark_harness.validate_skill_runtime_proof import validate as validate_skill_runtime_proof

WORKFLOW_ARTIFACT_NAMES = [
    "SPEC.md",
    "PLAN.md",
    "BUGS.md",
    "VERIFY.md",
    "HANDOFF.md",
    "SKILL_RUNTIME_PROOF.md",
]

DIFF_HEADER_RE = re.compile(r"^diff --git a/(?P<a>.+?) b/(?P<b>.+?)$", re.MULTILINE)

USAGE_LIMIT_MARKERS = [
    "reached max turns",
    "hit max turns",
    "max turns",
    "turn limit",
    "usage limit",
    "token limit",
    "out of turns",
]

ENVIRONMENT_MARKERS = [
    "command not found",
    "no such file or directory",
    "permission denied",
    "could not find",
    "failed to initialize",
    "unknown model",
    "invalid model",
    "model slug",
    "authentication",
    "api key",
    "rate limit",
    "connection refused",
    "sandbox blocked",
    "access denied",
    "missing pinned skill metadata",
    "skill plugin dir",
    "claude_plugin_dir",
]

AGENT_STOP_MARKERS = [
    "i can't",
    "i cannot",
    "unable to continue",
    "unable to comply",
    "not able to",
    "refuse",
    "refusing",
    "stopping here",
]

PROMPT_PROOF_MARKERS = [
    "SKILL_RUNTIME_PROOF.md",
    "Create `SKILL_RUNTIME_PROOF.md`",
    "create `SKILL_RUNTIME_PROOF.md`",
    "must use `SKILL_RUNTIME_PROOF.md`",
]

SKILL_CONTEXT_MARKERS = [
    "# Skill Runtime Context",
    "- Repo URL:",
    "- Pinned commit SHA:",
    "- Local plugin path:",
    "- Agent-visible plugin path:",
    "- Pre-run availability check command:",
    "- Pre-run availability check result:",
    "- Pre-run availability evidence path:",
    "- Task slug:",
    "- Arm slug:",
    "- Run ID:",
]


def arm_requires_skill_runtime(arm_slug: str) -> bool:
    return arm_slug.startswith("E-")


def _read_text(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _read_json(path: Path) -> dict[str, Any] | None:
    text = _read_text(path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _extract_changed_files(diff_patch_path: Path) -> list[str]:
    text = _read_text(diff_patch_path) or ""
    files: list[str] = []
    seen: set[str] = set()
    for match in DIFF_HEADER_RE.finditer(text):
        for candidate in (match.group("a"), match.group("b")):
            if candidate not in seen:
                seen.add(candidate)
                files.append(candidate)
    return files


def _workflow_artifacts_present(workspace_root: Path) -> list[str]:
    return [name for name in WORKFLOW_ARTIFACT_NAMES if (workspace_root / name).exists()]


def _proof_state(
    workspace_root: Path,
    *,
    expected_agent_cli: str | None = None,
) -> tuple[bool, bool, list[str]]:
    proof_path = workspace_root / "SKILL_RUNTIME_PROOF.md"
    if not proof_path.exists() or not proof_path.is_file():
        return False, False, ["missing SKILL_RUNTIME_PROOF.md"]
    try:
        issues = validate_skill_runtime_proof(
            proof_path,
            expected_agent_cli=expected_agent_cli,
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        return True, False, [f"{exc.__class__.__name__}: {exc}"]
    return True, not issues, issues


def _skill_context_state(workspace_root: Path) -> tuple[bool, bool, list[str]]:
    context_path = workspace_root / ".benchmark" / "SKILL_RUNTIME_CONTEXT.md"
    if not context_path.exists() or not context_path.is_file():
        return False, False, ["missing .benchmark/SKILL_RUNTIME_CONTEXT.md"]
    text = _read_text(context_path) or ""
    issues = [f"missing marker: {marker}" for marker in SKILL_CONTEXT_MARKERS if marker not in text]
    return True, not issues, issues


def _prompt_requires_proof(prompt_file: Path) -> bool:
    text = _read_text(prompt_file)
    return bool(text and any(marker in text for marker in PROMPT_PROOF_MARKERS))


def _initial_not_ready_state(run_dir: Path) -> dict[str, object]:
    path = run_dir / "INITIAL_NOT_READY.txt"
    text = _read_text(path)
    if text is None:
        return {"present": False, "skill_runtime_proof": None}

    proof_state = None
    match = re.search(
        r"^skill_runtime_proof\s*=\s*(\w+)\s*$",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    if match:
        proof_state = match.group(1).strip().lower()
    return {"present": True, "skill_runtime_proof": proof_state}


def _detect_markers(texts: list[str], markers: list[str]) -> bool:
    lowered = "\n".join(texts).lower()
    return any(marker in lowered for marker in markers)


def _load_output_texts(run_dir: Path) -> list[str]:
    names = (
        "codex_stdout.txt",
        "codex_stderr.txt",
        "verification_final.txt",
        "verification.txt",
        "hidden_evaluator_final.txt",
        "hidden_evaluator.txt",
        "INITIAL_NOT_READY.txt",
    )
    return [text for name in names if (text := _read_text(run_dir / name)) is not None]


def _build_public_status(classification: str, *, task_attempted: bool) -> str:
    mapping = {
        "completed_with_required_artifacts": "passed",
        "missing_skill_runtime_proof": "failed: missing proof after task attempt",
        "functional_failure": "failed: functional",
        "artifact_contract_failure": "failed: artifact contract",
        "harness_failure": "failed: harness",
        "environment_blocked_before_attempt": "blocked: environment before task attempt",
        "usage_limit_blocked_before_attempt": "blocked: usage limit before task attempt",
        "agent_stopped_before_attempt": "blocked: agent stopped before task attempt",
    }
    if classification == "skill_context_failure":
        return "blocked: skill context before task attempt" if not task_attempted else "failed: skill context"
    return mapping.get(classification, "unknown")


def _build_failure_category(classification: str) -> str | None:
    if classification == "completed_with_required_artifacts":
        return None
    if classification in {"missing_skill_runtime_proof", "artifact_contract_failure"}:
        return "artifact_contract_failure"
    if classification == "functional_failure":
        return "functional_failure"
    if classification == "skill_context_failure":
        return "skill_context_failure"
    if classification in {"environment_blocked_before_attempt", "usage_limit_blocked_before_attempt"}:
        return "environment_failure"
    if classification == "harness_failure":
        return "harness_gate_failure"
    return "unknown"


def _classify_recovery(
    *,
    skill_runtime_required: bool,
    proof_required: bool,
    prompt_explicit: bool,
    skill_context_present: bool,
    skill_context_valid: bool,
    proof_present: bool,
    proof_valid: bool,
    functional_green: bool,
    functional_known: bool,
    task_attempted: bool,
    usage_limit_blocked: bool,
    environment_blocked: bool,
    agent_stopped: bool,
    reached_max_turns: bool | str,
) -> str:
    del reached_max_turns
    if not task_attempted and usage_limit_blocked:
        return "usage_limit_blocked_before_attempt"
    if not task_attempted and environment_blocked:
        return "environment_blocked_before_attempt"
    if skill_runtime_required and (not skill_context_present or not skill_context_valid):
        return "skill_context_failure"
    if not task_attempted and agent_stopped:
        return "agent_stopped_before_attempt"
    if proof_required and not prompt_explicit:
        return "harness_failure"
    if not functional_known:
        return "harness_failure"
    if not functional_green:
        return "functional_failure"
    if proof_required and not proof_present:
        return "missing_skill_runtime_proof"
    if proof_required and not proof_valid:
        return "artifact_contract_failure"
    return "completed_with_required_artifacts"


def _artifact_status(*, proof_required: bool, proof_present: bool, proof_valid: bool) -> str:
    if not proof_required:
        return "not_required"
    if not proof_present:
        return "missing"
    return "passed" if proof_valid else "invalid"


def _render_markdown(recovery: dict[str, Any]) -> str:
    lines = [
        "# Skill Runtime Recovery",
        "",
        "## Run",
        f"- Run ID: {recovery['run_id']}",
        f"- Task: {recovery['task_slug']}",
        f"- Arm: {recovery['arm_slug']}",
        f"- Phase: {recovery['phase']}",
        f"- Prompt explicit: {'yes' if recovery['prompt_explicit'] else 'no'}",
        f"- Collect exit code: {recovery.get('collect_exit_code', 'unknown')}",
        f"- Codex exit code: {recovery.get('codex_exit_code', 'unknown')}",
        f"- Reached max turns: {recovery['reached_max_turns']}",
        "",
        "## Evidence",
        f"- Skill context present: {'yes' if recovery['skill_runtime_context_present'] else 'no'}",
        f"- Skill context valid: {'yes' if recovery['skill_runtime_context_valid'] else 'no'}",
        f"- Skill proof present: {'yes' if recovery['skill_runtime_proof_present'] else 'no'}",
        f"- Skill proof valid: {'yes' if recovery['skill_runtime_proof_valid'] else 'no'}",
        f"- Functional status: {recovery['functional_status']}",
        f"- Artifact status: {recovery['artifact_status']}",
        f"- Functional green: {'yes' if recovery['functional_green'] else 'no'}",
        f"- Task attempted: {'yes' if recovery['task_attempted'] else 'no'}",
        f"- Changed files: {', '.join(recovery['changed_files']) if recovery['changed_files'] else 'none'}",
        f"- Workflow artifacts: {', '.join(recovery['workflow_artifacts']) if recovery['workflow_artifacts'] else 'none'}",
        f"- INITIAL_NOT_READY present: {'yes' if recovery['initial_not_ready_present'] else 'no'}",
        f"- INITIAL_NOT_READY skill_runtime_proof: {recovery.get('initial_not_ready_skill_runtime_proof') or 'n/a'}",
        "",
        "## Classification",
        f"- Classification: {recovery['classification']}",
        f"- Public status: {recovery['public_status']}",
        f"- Failure category: {recovery['failure_category'] or 'none'}",
        f"- Stop after initial: {'yes' if recovery['stop_after_initial'] else 'no'}",
        f"- Failure reason: {recovery['failure_reason']}",
        "",
        "## Paths",
        f"- Prompt file: {recovery['prompt_file']}",
        f"- Verification file: {recovery['verification_file']}",
        f"- Hidden evaluator file: {recovery['hidden_evaluator_file']}",
        f"- Skill context file: {recovery['skill_context_file']}",
        f"- Skill proof file: {recovery['skill_runtime_proof_file']}",
        f"- Recovery JSON: {recovery['recovery_json_file']}",
        "",
    ]
    return "\n".join(lines)


def build_skill_runtime_recovery(
    *,
    run_dir: Path,
    workspace_root: Path,
    prompt_file: Path,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    collect_exit_code: int | None = None,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    workspace_root = workspace_root.resolve()
    prompt_file = prompt_file.resolve()
    run_metrics = _read_json(run_dir / "run_metrics.json") or {}
    run_provenance = _read_json(run_dir / "run_provenance.json") or {}
    expected_agent_cli = str(run_metrics.get("runner") or run_metrics.get("provider") or "").strip() or None

    verification_file = run_dir / ("verification_final.txt" if phase == "initial" else "verification.txt")
    hidden_evaluator_file = run_dir / ("hidden_evaluator_final.txt" if phase == "initial" else "hidden_evaluator.txt")
    diff_patch = run_dir / "diff.patch"
    diff_stat = run_dir / "diff_stat.txt"
    prompt_explicit = _prompt_requires_proof(prompt_file)

    skill_context_file = workspace_root / ".benchmark" / "SKILL_RUNTIME_CONTEXT.md"
    skill_context_present, skill_context_valid, skill_context_issues = _skill_context_state(workspace_root)
    skill_runtime_proof_file = workspace_root / "SKILL_RUNTIME_PROOF.md"
    proof_present, proof_valid, proof_issues = _proof_state(workspace_root, expected_agent_cli=expected_agent_cli)
    workflow_artifacts = _workflow_artifacts_present(workspace_root)
    changed_files = _extract_changed_files(diff_patch)
    initial_not_ready = _initial_not_ready_state(run_dir)
    output_texts = _load_output_texts(run_dir)

    verify_exit = infer_command_exit([verification_file, run_dir / "verification.txt", run_dir / "verification_final.txt"], "verify")
    hidden_exit = infer_command_exit([hidden_evaluator_file, run_dir / "hidden_evaluator.txt", run_dir / "hidden_evaluator_final.txt"], "hidden")
    functional_known = verify_exit in {0, 1} and hidden_exit in {0, 1}
    functional_green = functional_known and verify_exit == 0 and hidden_exit == 0
    functional_status = "passed" if functional_green else "failed" if functional_known else "unknown"

    actual_turns = _safe_int(run_metrics.get("actual_turns")) or _safe_int(run_metrics.get("num_turns"))
    codex_exit_code = _safe_int(run_metrics.get("runner_exit_code"))
    if codex_exit_code is None:
        codex_exit_code = _safe_int(run_metrics.get("agent_exit_code"))
    if codex_exit_code is None:
        codex_exit_code = _safe_int(_read_text(run_dir / "codex_exit_code.txt"))

    reached_max_turns = run_metrics.get("reached_max_turns", "unknown")
    if isinstance(reached_max_turns, str):
        normalized = reached_max_turns.strip().lower()
        if normalized in {"true", "false"}:
            reached_max_turns = normalized == "true"

    task_attempted = bool(changed_files or workflow_artifacts or proof_present or (actual_turns is not None and actual_turns > 0) or _file_size(diff_patch) > 0)
    usage_limit_blocked = bool(reached_max_turns is True or _detect_markers(output_texts, USAGE_LIMIT_MARKERS) or (initial_not_ready.get("skill_runtime_proof") == "missing" and not changed_files and not proof_present))
    environment_blocked = _detect_markers(output_texts, ENVIRONMENT_MARKERS)
    agent_stopped = _detect_markers(output_texts, AGENT_STOP_MARKERS)

    skill_runtime_required = arm_requires_skill_runtime(arm_slug)
    proof_required = skill_runtime_required
    classification = _classify_recovery(
        skill_runtime_required=skill_runtime_required,
        proof_required=proof_required,
        prompt_explicit=prompt_explicit,
        skill_context_present=skill_context_present,
        skill_context_valid=skill_context_valid,
        proof_present=proof_present,
        proof_valid=proof_valid,
        functional_green=functional_green,
        functional_known=functional_known,
        task_attempted=task_attempted,
        usage_limit_blocked=usage_limit_blocked,
        environment_blocked=environment_blocked,
        agent_stopped=agent_stopped,
        reached_max_turns=reached_max_turns,
    )
    artifact_status = _artifact_status(proof_required=proof_required, proof_present=proof_present, proof_valid=proof_valid)
    public_status = _build_public_status(classification, task_attempted=task_attempted)
    failure_category = _build_failure_category(classification)
    stop_after_initial = public_status.startswith("blocked:")
    if classification == "skill_context_failure" and phase == "initial":
        stop_after_initial = True

    evidence_paths = [
        str(prompt_file),
        str(verification_file),
        str(hidden_evaluator_file),
        str(skill_context_file),
        str(skill_runtime_proof_file),
        str(run_dir / "run_metrics.json"),
        str(run_dir / "run_provenance.json"),
        str(run_dir / "codex_stdout.txt"),
        str(run_dir / "codex_stderr.txt"),
        str(run_dir / "INITIAL_NOT_READY.txt"),
    ]

    failure_reason = public_status
    if classification == "functional_failure":
        reason = _read_text(hidden_evaluator_file)
        if reason:
            failure_reason = reason.strip().splitlines()[0]
    elif classification == "artifact_contract_failure" and proof_issues:
        failure_reason = proof_issues[0]
    elif classification == "harness_failure" and not functional_known:
        failure_reason = "verification or hidden evaluator status could not be determined"
    elif classification == "completed_with_required_artifacts":
        failure_reason = "passed"

    recovery: dict[str, Any] = {
        "schema_version": 2,
        "run_id": run_id,
        "task_slug": task_slug,
        "arm_slug": arm_slug,
        "phase": phase,
        "prompt_file": str(prompt_file),
        "verification_file": str(verification_file),
        "hidden_evaluator_file": str(hidden_evaluator_file),
        "skill_context_file": str(skill_context_file),
        "skill_runtime_proof_file": str(skill_runtime_proof_file),
        "recovery_json_file": str(run_dir / "skill_runtime_recovery.json"),
        "prompt_explicit": prompt_explicit,
        "collect_exit_code": collect_exit_code,
        "codex_exit_code": codex_exit_code,
        "reached_max_turns": reached_max_turns,
        "skill_runtime_context_present": skill_context_present,
        "skill_runtime_context_valid": skill_context_valid,
        "skill_runtime_context_issues": skill_context_issues,
        "skill_runtime_proof_present": proof_present,
        "skill_runtime_proof_valid": proof_valid,
        "skill_runtime_proof_issues": proof_issues,
        "workflow_artifacts": workflow_artifacts,
        "changed_files": changed_files,
        "changed_file_count": len(changed_files),
        "diff_bytes": _file_size(diff_patch),
        "diff_stat_bytes": _file_size(diff_stat),
        "verification_exit": verify_exit,
        "hidden_evaluator_exit": hidden_exit,
        "functional_known": functional_known,
        "functional_green": functional_green,
        "functional_status": functional_status,
        "artifact_status": artifact_status,
        "expected_agent_cli": expected_agent_cli,
        "task_attempted": task_attempted,
        "initial_not_ready_present": bool(initial_not_ready.get("present")),
        "initial_not_ready_skill_runtime_proof": initial_not_ready.get("skill_runtime_proof"),
        "proof_required": proof_required,
        "classification": classification,
        "public_status": public_status,
        "failure_category": failure_category,
        "stop_after_initial": stop_after_initial,
        "failure_reason": failure_reason,
        "evidence_paths": evidence_paths,
        "run_model": run_provenance.get("model"),
        "run_effort": run_provenance.get("effort"),
        "run_max_turns": run_provenance.get("max_turns"),
        "run_permission_mode": run_provenance.get("permission_mode"),
        "run_output_format": run_provenance.get("output_format") or run_metrics.get("output_format"),
        "run_label": run_provenance.get("label"),
    }

    _write_json(run_dir / "skill_runtime_recovery.json", recovery)
    _write_text(run_dir / "skill_runtime_recovery.md", _render_markdown(recovery))
    return recovery


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write deterministic recovery artifacts for a Codex pilot run.")
    parser.add_argument("command", choices=["write"])
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-slug", required=True)
    parser.add_argument("--arm-slug", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--collect-exit-code", type=int, default=None)
    args = parser.parse_args(argv)

    if args.command == "write":
        recovery = build_skill_runtime_recovery(
            run_dir=args.run_dir,
            workspace_root=args.workspace_root,
            prompt_file=args.prompt_file,
            run_id=args.run_id,
            task_slug=args.task_slug,
            arm_slug=args.arm_slug,
            phase=args.phase,
            collect_exit_code=args.collect_exit_code,
        )
        print(f"{args.run_dir / 'skill_runtime_recovery.json'} :: {recovery['public_status']}")
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
