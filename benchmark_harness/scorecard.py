from __future__ import annotations

import argparse
import csv
import json
import re
import tarfile
import tempfile
from pathlib import Path
from typing import Iterable

from benchmark_harness.semantic_terminal_state import classify_semantic_terminal_state
from benchmark_harness.solution_latency import summarize_solution_latency
from benchmark_harness.validate_skill_runtime_proof import validate as validate_skill_runtime_proof

WORKFLOW_ARTIFACT_NAMES = [
    "SPEC.md",
    "PLAN.md",
    "BUGS.md",
    "VERIFY.md",
    "HANDOFF.md",
    "SKILL_RUNTIME_PROOF.md",
]

EVAL_BUNDLE_KIND = "eval"
INITIAL_FAIL_BUNDLE_KIND = "initial_fail"

MECHANISM_ARTIFACT_NAMES = {
    "SPEC.md",
    "PLAN.md",
    "BUGS.md",
    "VERIFY.md",
    "HANDOFF.md",
    "SKILL_RUNTIME_PROOF.md",
}

SOLUTION_LATENCY_FIELDS = [
    "actual_turns",
    "first_green_turn",
    "turns_after_first_green",
    "permission_denials_after_first_green",
    "solution_latency_observable",
    "solution_latency_source",
    "solution_latency_note",
]

ROW_FIELDS = [
    "bundle",
    "run_id",
    "arm_slug",
    "bundle_type",
    "initial_ready",
    "initial_verify_exit",
    "initial_hidden_exit",
    "initial_green",
    "initial_terminal_reason",
    "initial_semantic_terminal_state",
    "initial_actual_turns",
    "initial_first_green_turn",
    "initial_turns_after_first_green",
    "initial_permission_denials_after_first_green",
    "initial_solution_latency_observable",
    "initial_solution_latency_source",
    "initial_solution_latency_note",
    "failure_stage",
    "failure_reason",
    "initial_diff_bytes",
    "initial_diff_files",
    "skill_runtime_proof_present",
    "skill_runtime_proof_valid",
    "workflow_artifacts_present",
    "workflow_artifacts",
    "stripped_removed_artifacts",
    "artifact_mechanism_active",
    "full_resume_verify_exit",
    "full_resume_hidden_exit",
    "full_resume_green",
    "full_resume_terminal_reason",
    "full_resume_semantic_terminal_state",
    "full_resume_actual_turns",
    "full_resume_first_green_turn",
    "full_resume_turns_after_first_green",
    "full_resume_permission_denials_after_first_green",
    "full_resume_solution_latency_observable",
    "full_resume_solution_latency_source",
    "full_resume_solution_latency_note",
    "stripped_resume_verify_exit",
    "stripped_resume_hidden_exit",
    "stripped_resume_green",
    "stripped_resume_terminal_reason",
    "stripped_resume_semantic_terminal_state",
    "stripped_resume_actual_turns",
    "stripped_resume_first_green_turn",
    "stripped_resume_turns_after_first_green",
    "stripped_resume_permission_denials_after_first_green",
    "stripped_resume_solution_latency_observable",
    "stripped_resume_solution_latency_source",
    "stripped_resume_solution_latency_note",
    "full_added_regression_test",
    "stripped_added_regression_test",
    "agent_side_verification_claim",
]

BUNDLE_NAME_RE = re.compile(r"^(?P<run_id>.+?)-(?P<bundle_kind>eval|initial-fail)-bundle(?:\.tar)?\.gz$")
DIFF_HEADER_RE = re.compile(r"^diff --git a/(?P<a>.+?) b/(?P<b>.+?)$", re.MULTILINE)


def _read_text(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _read_json(path: Path) -> dict[str, object] | None:
    text = _read_text(path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _skill_runtime_proof_valid(proof_path: Path) -> bool:
    if not proof_path.exists() or not proof_path.is_file():
        return False
    try:
        return not validate_skill_runtime_proof(proof_path)
    except OSError:
        return False


def _safe_extract_tarball(bundle_path: Path, dest_dir: Path) -> None:
    dest_root = dest_dir.resolve()
    with tarfile.open(bundle_path, mode="r:*") as tar:
        for member in tar.getmembers():
            if member.islnk() or member.issym():
                raise ValueError(f"refusing to extract symlink from bundle: {member.name}")
            target = (dest_root / member.name).resolve()
            try:
                target.relative_to(dest_root)
            except ValueError as exc:
                raise ValueError(f"bundle contains unsafe path: {member.name}") from exc
        tar.extractall(dest_root, filter="data")


def _infer_run_id(bundle_path: Path, extracted_root: Path) -> str:
    manifest = extracted_root / "benchmark-data" / "runs"
    if manifest.exists():
        candidates = sorted(manifest.glob("*/run_workspace_manifest.json"))
        if candidates:
            return candidates[0].parent.name
    match = BUNDLE_NAME_RE.match(bundle_path.name)
    if match:
        return match.group("run_id")
    return (
        bundle_path.name.removesuffix(".tar.gz")
        .removesuffix("-eval-bundle")
        .removesuffix("-initial-fail-bundle")
    )


def _bundle_type_from_bundle_path(bundle_path: Path) -> str:
    match = BUNDLE_NAME_RE.match(bundle_path.name)
    if match:
        return INITIAL_FAIL_BUNDLE_KIND if match.group("bundle_kind") == "initial-fail" else EVAL_BUNDLE_KIND
    if "initial-fail-bundle" in bundle_path.name:
        return INITIAL_FAIL_BUNDLE_KIND
    return EVAL_BUNDLE_KIND


def _arm_slug_from_run_id(run_id: str) -> str:
    if "_A_" in run_id:
        return "A-baseline"
    if "_E_" in run_id:
        return "E-ai-engineering-skills"
    return "unknown"


def _resume_candidate_paths(extracted_root: Path, run_id: str, stage: str, bundle_type: str) -> list[Path]:
    if bundle_type == INITIAL_FAIL_BUNDLE_KIND:
        return []
    if stage == "full":
        resume_root = extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full"
    else:
        resume_root = extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped"
    return [
        resume_root / "verification.txt",
        resume_root / "VERIFY.md",
        resume_root / "FRESH_SESSION_REVIEW.md",
        resume_root / "BUGFIX_REVIEW.md",
        resume_root / "HANDOFF.md",
        resume_root / "hidden_evaluator.txt",
        resume_root / "claude_stdout.txt",
        resume_root / "claude_stderr.txt",
    ]


def _resume_stage_exit(extracted_root: Path, run_id: str, stage: str, bundle_type: str, kind: str) -> int | str | None:
    candidate_paths = _resume_candidate_paths(extracted_root, run_id, stage, bundle_type)
    if not candidate_paths or not any(path.exists() for path in candidate_paths):
        return "not_run"
    return _infer_command_exit(candidate_paths, kind)


def _failure_reason_from_initial_run(initial_run: Path) -> str | None:
    for path_name in ("hidden_evaluator_final.txt", "hidden_evaluator.txt"):
        text = _read_text(initial_run / path_name)
        if text is None:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            match = re.match(r"^HIDDEN CONTRACT FAILED:\s*(.+)$", stripped, re.I)
            if match:
                reason = match.group(1).strip()
                return reason or None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
    return None


def _extract_explicit_exit(text: str, kind: str) -> int | None:
    lowered = text.lower()
    if kind == "verify":
        patterns = [
            r"\bverify(?:ication)?(?:_|-|\s)*exit(?:_|-|\s)*(?:code)?\s*[:=]\s*(0|1)\b",
            r"\bverify_exit\s*[:=]\s*(0|1)\b",
            r"\bverification_exit\s*[:=]\s*(0|1)\b",
        ]
    else:
        patterns = [
            r"\bhidden(?:_|-|\s)*evaluator(?:_|-|\s)*exit(?:_|-|\s)*(?:code)?\s*[:=]\s*(0|1)\b",
            r"\bhidden_evaluator_exit\s*[:=]\s*(0|1)\b",
        ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            return int(match.group(1))
    return None


def _infer_exit_from_output(text: str, kind: str) -> int | None:
    lowered = text.lower()
    if kind == "verify":
        fail_markers = [
            "traceback (most recent call last)",
            "assertionerror",
            "failed tests",
            "test session fails",
        ]
        fail_regexes = [
            r"^failed\b",
            r"\b[1-9]\d*\s+failed\b",
            r"^error\b",
            r"\b[1-9]\d*\s+errors?\b",
        ]
        pass_markers = [
            "passed in",
            "all tests passed",
            "no impossible churn detected",
            "verification passed",
            "verify.sh passed",
            "success",
        ]
    else:
        fail_markers = [
            "traceback (most recent call last)",
            "assertionerror",
        ]
        fail_regexes = [
            r"^hidden contract failed\b",
            r"^failed\b",
            r"\b[1-9]\d*\s+failed\b",
            r"^error\b",
            r"\b[1-9]\d*\s+errors?\b",
        ]
        pass_markers = [
            "hidden task 4 evaluator passed",
            "no hidden contract failed",
            "evaluator passed",
            "passed",
            "success",
        ]

    if any(marker in lowered for marker in fail_markers):
        return 1
    if any(re.search(pattern, lowered, flags=re.MULTILINE) for pattern in fail_regexes):
        return 1
    if any(marker in lowered for marker in pass_markers):
        return 0
    return None


def _infer_command_exit(candidate_paths: Iterable[Path], kind: str) -> int | None:
    texts: list[str] = []
    for path in candidate_paths:
        text = _read_text(path)
        if text is None:
            continue
        explicit = _extract_explicit_exit(text, kind)
        if explicit is not None:
            return explicit
        texts.append(text)
    for text in texts:
        inferred = _infer_exit_from_output(text, kind)
        if inferred is not None:
            return inferred
    return None


def _count_diff_files(diff_stat_path: Path, diff_patch_path: Path) -> int:
    diff_stat = _read_text(diff_stat_path)
    if diff_stat:
        match = re.search(r"(\d+)\s+files?\s+changed", diff_stat)
        if match:
            return int(match.group(1))
        match = re.search(r"(\d+)\s+file", diff_stat)
        if match:
            return int(match.group(1))

    patch_text = _read_text(diff_patch_path) or ""
    files = set()
    for match in DIFF_HEADER_RE.finditer(patch_text):
        files.add(match.group("a"))
    if files:
        return len(files)
    return sum(1 for line in patch_text.splitlines() if line.startswith("diff --git a/"))


def _detect_added_regression_test(diff_patch_path: Path) -> bool:
    patch_text = _read_text(diff_patch_path) or ""
    if not patch_text:
        return False

    test_file_present = False
    for match in DIFF_HEADER_RE.finditer(patch_text):
        paths = (match.group("a"), match.group("b"))
        if any(_looks_like_test_file(path) for path in paths):
            test_file_present = True
            break

    if not test_file_present:
        return False

    lowered = patch_text.lower()
    keywords = [
        "cancellation",
        "active interval",
        "active-interval",
        "plan history",
        "duplicate row",
        "duplicate rows",
        "churn",
    ]
    return any(keyword in lowered for keyword in keywords)


def _looks_like_test_file(path: str) -> bool:
    filename = Path(path).name
    return "/tests/" in path or path.startswith("tests/") or filename.startswith("test_")


def _bundle_workspace_paths(extracted_root: Path, run_id: str) -> dict[str, Path]:
    return {
        "initial_run": extracted_root / "benchmark-data" / "runs" / run_id,
        "initial_repo": extracted_root / "benchmark-data" / "workspaces" / run_id / "repo",
        "full_resume_run": extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full",
        "stripped_resume_run": extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped",
        "stripped_manifest": extracted_root
        / "benchmark-data"
        / "resume-workspaces"
        / run_id
        / "stripped"
        / "metadata"
        / "stripped_artifacts_manifest.json",
    }


def _workflow_artifacts_present(repo_root: Path) -> list[str]:
    present = []
    for name in WORKFLOW_ARTIFACT_NAMES:
        if (repo_root / name).exists():
            present.append(name)
    return present


def _read_stripped_removed_artifacts(manifest_path: Path) -> list[str]:
    data = _read_json(manifest_path)
    if not data:
        return []
    removed = data.get("removed", [])
    if not isinstance(removed, list):
        return []
    result = []
    for item in removed:
        if isinstance(item, str) and item:
            result.append(item)
    return result


def _agent_side_verification_claim(extracted_root: Path, run_id: str, *, initial_ready: bool) -> str:
    if not initial_ready:
        return "claimed_blocked"

    candidate_paths = [
        extracted_root / "benchmark-data" / "runs" / run_id / "claude_stdout.txt",
        extracted_root / "benchmark-data" / "runs" / run_id / "claude_stderr.txt",
        extracted_root / "benchmark-data" / "runs" / run_id / "verification_final.txt",
        extracted_root / "benchmark-data" / "runs" / run_id / "hidden_evaluator_final.txt",
        extracted_root / "benchmark-data" / "runs" / run_id / "INITIAL_NOT_READY.txt",
        extracted_root / "benchmark-data" / "runs" / run_id / "verification.txt",
        extracted_root / "benchmark-data" / "runs" / run_id / "hidden_evaluator.txt",
        extracted_root / "benchmark-data" / "workspaces" / run_id / "repo" / "VERIFY.md",
        extracted_root / "benchmark-data" / "workspaces" / run_id / "repo" / "HANDOFF.md",
        extracted_root / "benchmark-data" / "workspaces" / run_id / "repo" / "BUGS.md",
        extracted_root / "benchmark-data" / "workspaces" / run_id / "repo" / "SKILL_RUNTIME_PROOF.md",
        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "claude_stdout.txt",
        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "claude_stderr.txt",
        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "verification.txt",
        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "hidden_evaluator.txt",
        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "FRESH_SESSION_REVIEW.md",
        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "BUGFIX_REVIEW.md",
        extracted_root / "benchmark-data" / "resume-workspaces" / run_id / "full" / "repo" / "FRESH_SESSION_REVIEW.md",
        extracted_root / "benchmark-data" / "resume-workspaces" / run_id / "full" / "repo" / "BUGFIX_REVIEW.md",
        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "claude_stdout.txt",
        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "claude_stderr.txt",
        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "verification.txt",
        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "hidden_evaluator.txt",
        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "FRESH_SESSION_REVIEW.md",
        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "BUGFIX_REVIEW.md",
        extracted_root / "benchmark-data" / "resume-workspaces" / run_id / "stripped" / "repo" / "FRESH_SESSION_REVIEW.md",
        extracted_root / "benchmark-data" / "resume-workspaces" / run_id / "stripped" / "repo" / "BUGFIX_REVIEW.md",
    ]
    texts = [text for path in candidate_paths if (text := _read_text(path)) is not None]

    blocked_markers = [
        "could not run",
        "cannot run",
        "can't run",
        "blocked by sandbox",
        "permission denied",
        "requires interactive approval",
        "subprocess execution was blocked",
        "execution was blocked",
        "sandbox blocked",
        "not ready for resume testing",
    ]
    verified_markers = [
        "ran verify.sh",
        "ran verify",
        "ran pytest",
        "ran tests",
        "verified by",
        "verification passed",
        "tests passed",
        "regression command",
        "i ran",
        "i verified",
    ]

    blocked = any(marker in text.lower() for text in texts for marker in blocked_markers)
    verified = any(marker in text.lower() for text in texts for marker in verified_markers)

    if blocked:
        return "claimed_blocked"
    if verified:
        return "claimed_verified"
    return "unknown"


def _run_terminal_reason(run_dir: Path) -> str | None:
    data = _read_json(run_dir / "run_metrics.json")
    if not data:
        return None
    terminal_reason = data.get("terminal_reason")
    return terminal_reason if isinstance(terminal_reason, str) else None


def _stage_text(run_dir: Path) -> str:
    candidate_names = [
        "claude_stdout.txt",
        "claude_stderr.txt",
        "verification_final.txt",
        "hidden_evaluator_final.txt",
        "verification.txt",
        "hidden_evaluator.txt",
        "INITIAL_NOT_READY.txt",
        "FRESH_SESSION_REVIEW.md",
        "BUGFIX_REVIEW.md",
        "HANDOFF.md",
        "VERIFY.md",
    ]
    texts = []
    for name in candidate_names:
        text = _read_text(run_dir / name)
        if text is not None:
            texts.append(text)
    return "\n".join(texts)


def _file_size(path: Path) -> int:
    try:
        return len(path.read_bytes()) if path.exists() and path.is_file() else 0
    except OSError:
        return 0


def _semantic_stage_state(
    *,
    run_dir: Path,
    verify_exit: int | str | None,
    hidden_exit: int | str | None,
    diff_bytes: int,
    is_run: bool = True,
) -> str:
    if not is_run:
        return "not_run"
    return classify_semantic_terminal_state(
        terminal_reason=_run_terminal_reason(run_dir),
        verify_exit=verify_exit,
        hidden_exit=hidden_exit,
        diff_bytes=diff_bytes,
        text=_stage_text(run_dir),
    )


def _prefixed_latency(prefix: str, latency: dict[str, object]) -> dict[str, object]:
    return {f"{prefix}_{field}": latency.get(field) for field in SOLUTION_LATENCY_FIELDS}


def score_bundle(bundle_path: Path | str) -> dict[str, object]:
    bundle_path = Path(bundle_path)
    with tempfile.TemporaryDirectory(prefix="benchmark-scorecard-") as tmpdir:
        extracted_root = Path(tmpdir)
        _safe_extract_tarball(bundle_path, extracted_root)
        run_id = _infer_run_id(bundle_path, extracted_root)
        bundle_type = _bundle_type_from_bundle_path(bundle_path)
        paths = _bundle_workspace_paths(extracted_root, run_id)

        initial_repo = paths["initial_repo"]
        initial_run = paths["initial_run"]
        full_resume_run = paths["full_resume_run"]
        stripped_resume_run = paths["stripped_resume_run"]
        initial_not_ready = initial_run / "INITIAL_NOT_READY.txt"
        initial_ready = not initial_not_ready.exists()

        initial_verify_exit = _infer_command_exit(
            [initial_run / "verification_final.txt", initial_not_ready],
            "verify",
        )
        initial_hidden_exit = _infer_command_exit(
            [initial_run / "hidden_evaluator_final.txt", initial_not_ready],
            "hidden",
        )

        full_resume_verify_exit = _resume_stage_exit(extracted_root, run_id, "full", bundle_type, "verify")
        full_resume_hidden_exit = _resume_stage_exit(extracted_root, run_id, "full", bundle_type, "hidden")

        stripped_resume_verify_exit = _resume_stage_exit(extracted_root, run_id, "stripped", bundle_type, "verify")
        stripped_resume_hidden_exit = _resume_stage_exit(extracted_root, run_id, "stripped", bundle_type, "hidden")

        workflow_artifacts = _workflow_artifacts_present(initial_repo)
        stripped_removed_artifacts = _read_stripped_removed_artifacts(paths["stripped_manifest"])
        artifact_mechanism_active = bool(workflow_artifacts) and any(
            name in MECHANISM_ARTIFACT_NAMES for name in stripped_removed_artifacts
        )
        skill_runtime_proof_path = initial_repo / "SKILL_RUNTIME_PROOF.md"
        skill_runtime_proof_present = skill_runtime_proof_path.exists()
        skill_runtime_proof_valid = _skill_runtime_proof_valid(skill_runtime_proof_path)

        initial_diff_patch = initial_run / "diff.patch"
        initial_diff_stat = initial_run / "diff_stat.txt"
        initial_diff_bytes = _file_size(initial_diff_patch)

        full_resume_diff_bytes = _file_size(full_resume_run / "diff.patch")
        stripped_resume_diff_bytes = _file_size(stripped_resume_run / "diff.patch")
        full_resume_run_present = bundle_type != INITIAL_FAIL_BUNDLE_KIND and full_resume_run.exists()
        stripped_resume_run_present = bundle_type != INITIAL_FAIL_BUNDLE_KIND and stripped_resume_run.exists()

        initial_green = initial_verify_exit == 0 and initial_hidden_exit == 0
        full_resume_green = full_resume_verify_exit == 0 and full_resume_hidden_exit == 0
        stripped_resume_green = stripped_resume_verify_exit == 0 and stripped_resume_hidden_exit == 0

        initial_latency = summarize_solution_latency(
            initial_run,
            verify_exit=initial_verify_exit,
            hidden_exit=initial_hidden_exit,
        )
        full_resume_latency = summarize_solution_latency(
            full_resume_run,
            verify_exit=full_resume_verify_exit,
            hidden_exit=full_resume_hidden_exit,
        )
        stripped_resume_latency = summarize_solution_latency(
            stripped_resume_run,
            verify_exit=stripped_resume_verify_exit,
            hidden_exit=stripped_resume_hidden_exit,
        )

        row = {
            "bundle": str(bundle_path),
            "run_id": run_id,
            "arm_slug": _arm_slug_from_run_id(run_id),
            "bundle_type": bundle_type,
            "initial_ready": initial_ready,
            "initial_verify_exit": initial_verify_exit,
            "initial_hidden_exit": initial_hidden_exit,
            "initial_green": initial_green,
            "initial_terminal_reason": _run_terminal_reason(initial_run),
            "initial_semantic_terminal_state": _semantic_stage_state(
                run_dir=initial_run,
                verify_exit=initial_verify_exit,
                hidden_exit=initial_hidden_exit,
                diff_bytes=initial_diff_bytes,
            ),
            **_prefixed_latency("initial", initial_latency),
            "failure_stage": None if initial_ready else "initial",
            "failure_reason": _failure_reason_from_initial_run(initial_run) if not initial_ready else None,
            "initial_diff_bytes": initial_diff_bytes,
            "initial_diff_files": _count_diff_files(initial_diff_stat, initial_diff_patch),
            "skill_runtime_proof_present": skill_runtime_proof_present,
            "skill_runtime_proof_valid": skill_runtime_proof_valid,
            "workflow_artifacts_present": bool(workflow_artifacts),
            "workflow_artifacts": ";".join(workflow_artifacts),
            "stripped_removed_artifacts": ";".join(stripped_removed_artifacts),
            "artifact_mechanism_active": artifact_mechanism_active,
            "full_resume_verify_exit": full_resume_verify_exit,
            "full_resume_hidden_exit": full_resume_hidden_exit,
            "full_resume_green": full_resume_green,
            "full_resume_terminal_reason": _run_terminal_reason(full_resume_run) if full_resume_run_present else None,
            "full_resume_semantic_terminal_state": _semantic_stage_state(
                run_dir=full_resume_run,
                verify_exit=full_resume_verify_exit,
                hidden_exit=full_resume_hidden_exit,
                diff_bytes=full_resume_diff_bytes,
                is_run=full_resume_run_present,
            ),
            **_prefixed_latency("full_resume", full_resume_latency),
            "stripped_resume_verify_exit": stripped_resume_verify_exit,
            "stripped_resume_hidden_exit": stripped_resume_hidden_exit,
            "stripped_resume_green": stripped_resume_green,
            "stripped_resume_terminal_reason": _run_terminal_reason(stripped_resume_run) if stripped_resume_run_present else None,
            "stripped_resume_semantic_terminal_state": _semantic_stage_state(
                run_dir=stripped_resume_run,
                verify_exit=stripped_resume_verify_exit,
                hidden_exit=stripped_resume_hidden_exit,
                diff_bytes=stripped_resume_diff_bytes,
                is_run=stripped_resume_run_present,
            ),
            **_prefixed_latency("stripped_resume", stripped_resume_latency),
            "full_added_regression_test": _detect_added_regression_test(full_resume_run / "diff.patch"),
            "stripped_added_regression_test": _detect_added_regression_test(stripped_resume_run / "diff.patch"),
            "agent_side_verification_claim": _agent_side_verification_claim(
                extracted_root,
                run_id,
                initial_ready=initial_ready,
            ),
        }
        return row


def score_bundles(bundle_paths: Iterable[Path | str]) -> list[dict[str, object]]:
    return [score_bundle(path) for path in bundle_paths]


def _format_cell(value: object) -> str:
    if value is None:
        return "?"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).replace("\n", " ").replace("|", r"\|")


def render_markdown_table(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "| no rows |"
    headers = ROW_FIELDS
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_format_cell(row.get(field)) for field in headers) + " |")
    return "\n".join(lines)


def write_csv(rows: list[dict[str, object]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ROW_FIELDS)
        writer.writeheader()
        for row in rows:
            serialized = {}
            for field in ROW_FIELDS:
                value = row.get(field)
                if value is None:
                    serialized[field] = ""
                elif isinstance(value, bool):
                    serialized[field] = "true" if value else "false"
                else:
                    serialized[field] = str(value)
            writer.writerow(serialized)


def write_json(rows: list[dict[str, object]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a scorecard from one or more benchmark bundles.")
    parser.add_argument("bundles", nargs="+", help="One or more *-eval-bundle.tar.gz or *-initial-fail-bundle.tar.gz files")
    parser.add_argument("--out", dest="csv_out", default=None, help="Write a CSV scorecard to this path")
    parser.add_argument("--json-out", dest="json_out", default=None, help="Write a JSON scorecard to this path")
    args = parser.parse_args(argv)

    rows = score_bundles(args.bundles)
    table = render_markdown_table(rows)
    print(table)

    if args.csv_out:
        write_csv(rows, Path(args.csv_out))
    if args.json_out:
        write_json(rows, Path(args.json_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
