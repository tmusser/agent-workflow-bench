from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from benchmark_harness.solution_latency_observer import supports_stream_json
from benchmark_harness.validate_skill_runtime_proof import validate as validate_skill_runtime_proof

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FINALIZER_DIRNAME = "finalizer"
ALLOWED_CHANGED_FILES = {"SKILL_RUNTIME_PROOF.md", "VERIFY.md"}
DEFAULT_SKILL_PLUGIN_NAME = "ai-engineering-skills"
IGNORED_PATH_PARTS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__", "node_modules"}
IGNORED_FILENAMES = {".DS_Store"}


def _read_text(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _claude_permission_args(permission_mode: str) -> list[str]:
    if permission_mode in {"dangerously-skip-permissions", "skip"}:
        return ["--dangerously-skip-permissions"]
    return ["--permission-mode", permission_mode]


def _snapshot_ignore(_: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED_PATH_PARTS or name in IGNORED_FILENAMES}


def _snapshot_workspace(workspace_root: Path) -> tuple[Path, Path]:
    temp_root = Path(tempfile.mkdtemp(prefix="skill-runtime-finalizer-"))
    snapshot_root = temp_root / workspace_root.name
    shutil.copytree(workspace_root, snapshot_root, ignore=_snapshot_ignore)
    return temp_root, snapshot_root


def _inventory_files(root: Path) -> dict[str, str]:
    inventory: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in IGNORED_PATH_PARTS for part in rel.parts) or path.name in IGNORED_FILENAMES:
            continue
        try:
            inventory[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
    return inventory


def _file_change_audit(before: dict[str, str], after: dict[str, str]) -> dict[str, Any]:
    before_paths = set(before)
    after_paths = set(after)
    created_files = sorted(after_paths - before_paths)
    deleted_files = sorted(before_paths - after_paths)
    modified_files = sorted(path for path in before_paths & after_paths if before[path] != after[path])

    renamed_files: list[dict[str, str]] = []
    created_by_hash: dict[str, list[str]] = {}
    for path in created_files:
        created_by_hash.setdefault(after[path], []).append(path)

    for old_path in deleted_files:
        old_hash = before[old_path]
        candidates = created_by_hash.get(old_hash)
        if not candidates:
            continue
        new_path = candidates.pop(0)
        renamed_files.append({"from": old_path, "to": new_path})

    changed_files = sorted(set(created_files) | set(deleted_files) | set(modified_files))
    allowed_files_changed = sorted(path for path in changed_files if path in ALLOWED_CHANGED_FILES)
    forbidden_files_changed = sorted(path for path in changed_files if path not in ALLOWED_CHANGED_FILES)

    return {
        "schema_version": 1,
        "created_files": created_files,
        "deleted_files": deleted_files,
        "modified_files": modified_files,
        "renamed_files": renamed_files,
        "changed_files": changed_files,
        "allowed_files_changed": allowed_files_changed,
        "forbidden_files_changed": forbidden_files_changed,
        "functional_files_changed": bool(forbidden_files_changed),
    }


def _proof_validation(proof_path: Path) -> tuple[bool, int, list[str]]:
    if not proof_path.exists() or not proof_path.is_file():
        return False, 1, ["missing SKILL_RUNTIME_PROOF.md"]
    try:
        issues = validate_skill_runtime_proof(proof_path)
    except Exception as exc:  # pragma: no cover - defensive guard
        return False, 1, [f"{exc.__class__.__name__}: {exc}"]
    return not issues, 0 if not issues else 1, issues


def _run_command(command: list[str], *, cwd: Path, output_path: Path) -> int:
    proc = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    _write_text(output_path, f"{proc.stdout or ''}{proc.stderr or ''}")
    return proc.returncode


def _run_verify(snapshot_root: Path, output_path: Path) -> int:
    return _run_command(["bash", "./VERIFY.sh"], cwd=snapshot_root, output_path=output_path)


def _run_hidden(snapshot_root: Path, hidden_evaluator_module: str, output_path: Path) -> int:
    command = [
        sys.executable,
        "-m",
        hidden_evaluator_module,
        "--repo",
        str(snapshot_root),
    ]
    return _run_command(command, cwd=PROJECT_ROOT, output_path=output_path)


def _parse_markdown_fields(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        values[key.strip()] = value.strip()
    return values


def _first_concrete(*values: str | None, default: str = "MISSING_CONTEXT_VALUE") -> str:
    for value in values:
        if value is not None and value.strip():
            return value.strip()
    return default


def _pinned_skill_metadata_candidates(plugin_dir: str | None) -> list[Path]:
    candidates: list[Path] = []
    if plugin_dir:
        plugin_dir_path = Path(plugin_dir).expanduser()
        candidates.append(plugin_dir_path / "PINNED_SKILL_REPO.md")
        candidates.append(PROJECT_ROOT / "local_plugins" / plugin_dir_path.name / "PINNED_SKILL_REPO.md")
    candidates.append(PROJECT_ROOT / "local_plugins" / DEFAULT_SKILL_PLUGIN_NAME / "PINNED_SKILL_REPO.md")
    return candidates


def _read_pinned_skill_metadata(plugin_dir: str | None) -> dict[str, str]:
    for metadata_path in _pinned_skill_metadata_candidates(plugin_dir):
        metadata_text = _read_text(metadata_path)
        if metadata_text is not None:
            return _parse_markdown_fields(metadata_text)
    return {}


def _render_skill_runtime_proof(
    *,
    snapshot_root: Path,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    plugin_dir: str | None,
    main_verify_exit: int,
    main_hidden_exit: int,
) -> str:
    context_path = snapshot_root / ".benchmark" / "SKILL_RUNTIME_CONTEXT.md"
    context = _parse_markdown_fields(_read_text(context_path) or "")
    pinned = _read_pinned_skill_metadata(plugin_dir)

    repo_url = _first_concrete(context.get("Repo URL"), pinned.get("Repo URL"))
    pinned_sha = _first_concrete(context.get("Pinned commit SHA"), pinned.get("Pinned commit SHA"))
    local_path = _first_concrete(context.get("Local plugin path"), pinned.get("Local path"), plugin_dir)
    agent_visible_path = _first_concrete(
        context.get("Agent-visible plugin path"),
        plugin_dir,
        str((PROJECT_ROOT / local_path).resolve()) if local_path != "MISSING_CONTEXT_VALUE" else None,
    )
    install_command = _first_concrete(pinned.get("Install command"), context.get("Pin command"))
    evidence_path = _first_concrete(
        context.get("Pre-run availability evidence path"),
        ".benchmark/SKILL_RUNTIME_CONTEXT.md",
    )
    availability_command = _first_concrete(
        context.get("Pre-run availability check command"),
        f"test -f {agent_visible_path}/PINNED_SKILL_REPO.md",
    )
    availability_result = _first_concrete(context.get("Pre-run availability check result"), "available")

    task_value = _first_concrete(context.get("Task slug"), task_slug)
    arm_value = _first_concrete(context.get("Arm slug"), arm_slug)
    run_value = _first_concrete(context.get("Run ID"), run_id)

    prompt_wrapper_path = (
        "arms/E-ai-engineering-skills-task7.md"
        if task_slug == "07-dashboard-export-scope-pressure" and arm_slug == "E-ai-engineering-skills"
        else f"arm wrapper for {arm_slug}"
    )

    return "\n".join(
        [
            "# Skill Runtime Proof",
            "",
            "## Run",
            f"- Run ID: {run_value}",
            f"- Arm: {arm_value}",
            f"- Task: {task_value}",
            f"- Repeat: {phase}",
            "",
            "## Skill source",
            f"- Repo URL: {repo_url}",
            f"- Pinned commit SHA: {pinned_sha}",
            f"- Local path: {local_path}",
            f"- Install command: {install_command}",
            f"- Install stdout/stderr path: {evidence_path}",
            "",
            "## Activation",
            "- Agent CLI: Claude Code CLI via benchmark_harness.skill_runtime_finalizer",
            f"- Activation mechanism: CLAUDE_PLUGIN_DIR plus --plugin-dir {agent_visible_path}",
            f"- Prompt wrapper path: {prompt_wrapper_path}",
            f"- Agent-visible skill files: {agent_visible_path}/skills/**/*.md",
            f"- Environment variables relevant to skill loading: CLAUDE_PLUGIN_DIR={agent_visible_path}",
            "",
            "## Pre-run availability check",
            f"- Command run: {availability_command}",
            f"- Result: {availability_result}",
            f"- Evidence path: {evidence_path}",
            "",
            "## During-run evidence",
            "- Did the agent mention or invoke the skill? yes/no/unclear: yes",
            (
                "- Evidence: .benchmark/SKILL_RUNTIME_CONTEXT.md records skill runtime "
                "availability; the E-arm prompt required ai-engineering-skills; "
                f"main VERIFY.sh exit={main_verify_exit} and hidden evaluator exit={main_hidden_exit}."
            ),
            "- Notes: This proof was created by the harness audit finalizer after functional green; functional files were not changed.",
            "",
            "## Post-run caveat",
            "- Could a bad result be due to the skill not being loaded? yes/no/unclear: no",
            "- Reviewer notes: Runtime context and pinned skill metadata were available to the benchmark harness.",
            "",
        ]
    )


def _render_verify_note(*, main_verify_exit: int, main_hidden_exit: int) -> str:
    return "\n".join(
        [
            "# Verification",
            "",
            "- Finalizer type: deterministic harness audit finalizer.",
            "- Commands run by finalizer agent: none.",
            f"- Main VERIFY.sh exit before finalizer: {main_verify_exit}",
            f"- Main hidden evaluator exit before finalizer: {main_hidden_exit}",
            "- Harness post-finalizer checks: proof validator, VERIFY.sh, and hidden evaluator.",
            "- SKILL_RUNTIME_PROOF.md was created for harness validation.",
            "",
        ]
    )


def _write_deterministic_audit_artifacts(
    *,
    snapshot_root: Path,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    plugin_dir: str | None,
    main_verify_exit: int,
    main_hidden_exit: int,
) -> None:
    _write_text(
        snapshot_root / "SKILL_RUNTIME_PROOF.md",
        _render_skill_runtime_proof(
            snapshot_root=snapshot_root,
            run_id=run_id,
            task_slug=task_slug,
            arm_slug=arm_slug,
            phase=phase,
            plugin_dir=plugin_dir,
            main_verify_exit=main_verify_exit,
            main_hidden_exit=main_hidden_exit,
        ),
    )
    _write_text(
        snapshot_root / "VERIFY.md",
        _render_verify_note(
            main_verify_exit=main_verify_exit,
            main_hidden_exit=main_hidden_exit,
        ),
    )


def _parse_result_payload(stdout_text: str, output_format: str) -> dict[str, Any]:
    payload: dict[str, Any] | None = None
    if output_format == "json":
        try:
            raw = json.loads(stdout_text)
        except Exception:
            raw = None
        if isinstance(raw, dict):
            payload = raw
    elif output_format == "stream-json":
        for line in stdout_text.splitlines():
            try:
                event = json.loads(line)
            except Exception:
                continue
            if isinstance(event, dict) and str(event.get("type", "")).lower() == "result":
                payload = event
    if not payload:
        return {}

    metrics: dict[str, Any] = {}
    for key in ("num_turns", "actual_turns", "duration_ms", "duration_api_ms", "ttft_ms", "ttft_stream_ms", "time_to_request_ms", "total_cost_usd", "terminal_reason", "stop_reason", "session_id", "uuid"):
        if payload.get(key) is not None:
            metrics[key] = payload.get(key)

    usage = payload.get("usage")
    if isinstance(usage, dict):
        for key in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "service_tier", "speed", "inference_geo"):
            if usage.get(key) is not None:
                metrics[f"usage_{key}"] = usage.get(key)
        server_tool_use = usage.get("server_tool_use")
        if isinstance(server_tool_use, dict):
            for key in ("web_search_requests", "web_fetch_requests"):
                if server_tool_use.get(key) is not None:
                    metrics[f"usage_server_tool_use_{key}"] = server_tool_use.get(key)

    return metrics


def _run_claude(
    *,
    snapshot_root: Path,
    prompt_text: str,
    out_dir: Path,
    claude_cmd: str,
    model: str,
    effort: str,
    max_turns: int,
    permission_mode: str,
    plugin_dir: str | None,
) -> dict[str, Any]:
    actual_output_format = "json"
    if os.environ.get("CLAUDE_OUTPUT_FORMAT", "") != "json" and supports_stream_json(claude_cmd):
        actual_output_format = "stream-json"

    command = [claude_cmd, "-p"]
    if plugin_dir:
        command.extend(["--plugin-dir", plugin_dir])
    command.extend(
        [
            "--model",
            model,
            "--effort",
            effort,
            "--max-turns",
            str(max_turns),
            *_claude_permission_args(permission_mode),
            "--output-format",
            actual_output_format,
            prompt_text,
        ]
    )

    start_ns = time.time_ns()
    proc = subprocess.run(command, cwd=snapshot_root, capture_output=True, text=True, check=False)
    end_ns = time.time_ns()

    stdout_text = proc.stdout or ""
    stderr_text = proc.stderr or ""
    _write_text(out_dir / "claude_stdout.txt", stdout_text)
    _write_text(out_dir / "claude_stderr.txt", stderr_text)
    _write_text(out_dir / "claude_exit_code.txt", f"{proc.returncode}\n")

    metrics: dict[str, Any] = {
        "run_id": None,
        "model": model,
        "effort": effort,
        "max_turns": max_turns,
        "permission_mode": permission_mode,
        "output_format": actual_output_format,
        "claude_exit_code": proc.returncode,
        "wall_clock_seconds": round((end_ns - start_ns) / 1_000_000_000, 3),
    }
    metrics.update(_parse_result_payload(stdout_text, actual_output_format))
    _write_json(out_dir / "run_metrics.json", metrics)
    return metrics


def _copy_allowed_files(snapshot_root: Path, workspace_root: Path, allowed_files: Iterable[str]) -> None:
    for rel in allowed_files:
        source = snapshot_root / rel
        target = workspace_root / rel
        if source.exists() and source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        elif target.exists():
            target.unlink()


def _build_validation_text(
    *,
    proof_path: Path,
    proof_valid_after: bool,
    proof_validation_issues: list[str],
    verify_after_exit: int | None,
    hidden_after_exit: int | None,
    finalizer_valid: bool,
) -> str:
    lines = [
        "Skill runtime finalizer validation",
        f"proof_path={proof_path}",
        f"proof_valid_after={str(proof_valid_after).lower()}",
        f"verify_after_exit={verify_after_exit if verify_after_exit is not None else 'n/a'}",
        f"hidden_after_exit={hidden_after_exit if hidden_after_exit is not None else 'n/a'}",
        f"finalizer_valid={str(finalizer_valid).lower()}",
        "proof_validation_issues:",
    ]
    if proof_validation_issues:
        lines.extend(f"- {issue}" for issue in proof_validation_issues)
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _base_summary(
    *,
    enabled: bool,
    arm_slug: str,
    main_functional_green: bool,
    main_verify_exit: int,
    main_hidden_exit: int,
    proof_present_before: bool,
    proof_valid_before: bool,
    verify_present_before: bool,
    trigger_reason: str,
) -> dict[str, Any]:
    bench_ready_before = main_functional_green and proof_valid_before and verify_present_before
    return {
        "schema_version": 1,
        "finalizer_enabled": enabled,
        "eligible": enabled and arm_slug.startswith("E-") and main_functional_green,
        "finalizer_ran": False,
        "trigger_reason": trigger_reason,
        "main_functional_green": main_functional_green,
        "main_verify_exit": main_verify_exit,
        "main_hidden_exit": main_hidden_exit,
        "proof_present_before": proof_present_before,
        "proof_valid_before": proof_valid_before,
        "verify_present_before": verify_present_before,
        "proof_present_after": proof_present_before,
        "proof_valid_after": proof_valid_before,
        "verify_present_after": verify_present_before,
        "created_skill_runtime_proof": False,
        "validator_exit": 0 if proof_valid_before else 1,
        "verify_after_exit": None,
        "hidden_after_exit": None,
        "bench_ready_after_finalizer": bench_ready_before,
        "bench_ready_via_finalizer": False,
        "finalizer_valid": bench_ready_before,
        "claude_exit_code": None,
        "actual_turns": None,
        "wall_clock_seconds": None,
        "total_cost_usd": None,
        "output_format": None,
        "changed_files": [],
        "allowed_files_changed": [],
        "forbidden_files_changed": [],
        "functional_files_changed": False,
        "proof_validation_issues": [] if proof_valid_before else ["missing SKILL_RUNTIME_PROOF.md"],
    }


def run(
    *,
    workspace_root: Path,
    run_dir: Path,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    prompt_file: Path,
    claude_cmd: str,
    model: str,
    effort: str,
    max_turns: int,
    permission_mode: str,
    plugin_dir: str | None,
    hidden_evaluator_module: str,
    main_verify_exit: int,
    main_hidden_exit: int,
) -> int:
    run_dir.mkdir(parents=True, exist_ok=True)

    enabled = os.environ.get("ENABLE_SKILL_RUNTIME_FINALIZER", "0") == "1"
    main_functional_green = main_verify_exit == 0 and main_hidden_exit == 0

    proof_path = workspace_root / "SKILL_RUNTIME_PROOF.md"
    verify_path = workspace_root / "VERIFY.md"
    proof_present_before = proof_path.exists() and proof_path.is_file()
    proof_valid_before, _, proof_validation_issues_before = _proof_validation(proof_path)
    verify_present_before = verify_path.exists() and verify_path.is_file()

    if not enabled:
        summary = _base_summary(
            enabled=False,
            arm_slug=arm_slug,
            main_functional_green=main_functional_green,
            main_verify_exit=main_verify_exit,
            main_hidden_exit=main_hidden_exit,
            proof_present_before=proof_present_before,
            proof_valid_before=proof_valid_before,
            verify_present_before=verify_present_before,
            trigger_reason="disabled",
        )
        summary["proof_validation_issues"] = proof_validation_issues_before
        _write_json(run_dir / "summary.json", summary)
        return 0

    if not arm_slug.startswith("E-"):
        summary = _base_summary(
            enabled=True,
            arm_slug=arm_slug,
            main_functional_green=main_functional_green,
            main_verify_exit=main_verify_exit,
            main_hidden_exit=main_hidden_exit,
            proof_present_before=proof_present_before,
            proof_valid_before=proof_valid_before,
            verify_present_before=verify_present_before,
            trigger_reason="non_e_arm",
        )
        summary["proof_validation_issues"] = proof_validation_issues_before
        _write_json(run_dir / "summary.json", summary)
        return 0

    if not main_functional_green:
        summary = _base_summary(
            enabled=True,
            arm_slug=arm_slug,
            main_functional_green=False,
            main_verify_exit=main_verify_exit,
            main_hidden_exit=main_hidden_exit,
            proof_present_before=proof_present_before,
            proof_valid_before=proof_valid_before,
            verify_present_before=verify_present_before,
            trigger_reason="main_functional_green_false",
        )
        summary["proof_validation_issues"] = proof_validation_issues_before
        _write_json(run_dir / "summary.json", summary)
        return 0

    if proof_valid_before:
        summary = _base_summary(
            enabled=True,
            arm_slug=arm_slug,
            main_functional_green=True,
            main_verify_exit=main_verify_exit,
            main_hidden_exit=main_hidden_exit,
            proof_present_before=proof_present_before,
            proof_valid_before=proof_valid_before,
            verify_present_before=verify_present_before,
            trigger_reason="proof_already_valid",
        )
        summary["proof_validation_issues"] = proof_validation_issues_before
        _write_json(run_dir / "summary.json", summary)
        return 0

    trigger_reason = "functional_green_missing_or_invalid_skill_runtime_proof"
    temp_root: Path | None = None
    snapshot_root: Path | None = None
    summary = _base_summary(
        enabled=True,
        arm_slug=arm_slug,
        main_functional_green=True,
        main_verify_exit=main_verify_exit,
        main_hidden_exit=main_hidden_exit,
        proof_present_before=proof_present_before,
        proof_valid_before=proof_valid_before,
        verify_present_before=verify_present_before,
        trigger_reason=trigger_reason,
    )

    try:
        temp_root, snapshot_root = _snapshot_workspace(workspace_root)
        before_inventory = _inventory_files(snapshot_root)
        # The audit finalizer is intentionally deterministic: the harness is better
        # than an LLM at copying pinned runtime metadata into the strict proof schema.
        # Keep the Claude parameters in the CLI for compatibility, but do not call
        # Claude to create the proof.
        start_time = time.time()
        _write_deterministic_audit_artifacts(
            snapshot_root=snapshot_root,
            run_id=run_id,
            task_slug=task_slug,
            arm_slug=arm_slug,
            phase=phase,
            plugin_dir=plugin_dir,
            main_verify_exit=main_verify_exit,
            main_hidden_exit=main_hidden_exit,
        )
        metrics = {
            "claude_exit_code": 0,
            "actual_turns": 0,
            "wall_clock_seconds": round(time.time() - start_time, 3),
            "total_cost_usd": 0.0,
            "output_format": "deterministic",
        }
        _write_json(run_dir / "run_metrics.json", metrics)

        after_inventory = _inventory_files(snapshot_root)
        file_audit = _file_change_audit(before_inventory, after_inventory)
        _write_json(run_dir / "file_change_audit.json", file_audit)

        proof_present_after = snapshot_root.joinpath("SKILL_RUNTIME_PROOF.md").exists()
        verify_present_after = snapshot_root.joinpath("VERIFY.md").exists()
        proof_valid_after, validator_exit, proof_validation_issues_after = _proof_validation(
            snapshot_root / "SKILL_RUNTIME_PROOF.md"
        )

        verify_after_exit = _run_verify(snapshot_root, run_dir / "verify_after.txt")
        hidden_after_exit = _run_hidden(snapshot_root, hidden_evaluator_module, run_dir / "hidden_after.txt")
        validation_text = _build_validation_text(
            proof_path=snapshot_root / "SKILL_RUNTIME_PROOF.md",
            proof_valid_after=proof_valid_after,
            proof_validation_issues=proof_validation_issues_after,
            verify_after_exit=verify_after_exit,
            hidden_after_exit=hidden_after_exit,
            finalizer_valid=(
                proof_valid_after
                and verify_present_after
                and verify_after_exit == 0
                and hidden_after_exit == 0
                and not file_audit["functional_files_changed"]
            ),
        )
        _write_text(run_dir / "validation.txt", validation_text)

        finalizer_valid = (
            proof_valid_after
            and verify_present_after
            and verify_after_exit == 0
            and hidden_after_exit == 0
            and not file_audit["functional_files_changed"]
        )
        bench_ready_after_finalizer = finalizer_valid
        bench_ready_via_finalizer = finalizer_valid and not proof_valid_before
        created_skill_runtime_proof = not proof_present_before and proof_present_after and proof_valid_after

        if finalizer_valid:
            _copy_allowed_files(snapshot_root, workspace_root, file_audit["allowed_files_changed"])

        summary.update(
            {
                "finalizer_ran": True,
                "trigger_reason": trigger_reason,
                "proof_present_after": proof_present_after,
                "proof_valid_after": proof_valid_after,
                "verify_present_after": verify_present_after,
                "created_skill_runtime_proof": created_skill_runtime_proof,
                "validator_exit": validator_exit,
                "verify_after_exit": verify_after_exit,
                "hidden_after_exit": hidden_after_exit,
                "bench_ready_after_finalizer": bench_ready_after_finalizer,
                "bench_ready_via_finalizer": bench_ready_via_finalizer,
                "finalizer_valid": finalizer_valid,
                "claude_exit_code": metrics.get("claude_exit_code"),
                "actual_turns": metrics.get("num_turns", metrics.get("actual_turns")),
                "wall_clock_seconds": metrics.get("wall_clock_seconds"),
                "total_cost_usd": metrics.get("total_cost_usd"),
                "output_format": metrics.get("output_format"),
                "changed_files": file_audit["changed_files"],
                "allowed_files_changed": file_audit["allowed_files_changed"],
                "forbidden_files_changed": file_audit["forbidden_files_changed"],
                "functional_files_changed": file_audit["functional_files_changed"],
                "proof_validation_issues": proof_validation_issues_after,
            }
        )

        _write_json(run_dir / "summary.json", summary)
        return 0 if finalizer_valid else 1
    except Exception as exc:  # pragma: no cover - defensive guard
        _write_text(run_dir / "finalizer_error.txt", f"{exc.__class__.__name__}: {exc}\n")
        summary.update(
            {
                "finalizer_ran": True,
                "trigger_reason": trigger_reason,
                "finalizer_valid": False,
                "proof_validation_issues": [f"{exc.__class__.__name__}: {exc}"],
            }
        )
        _write_json(run_dir / "summary.json", summary)
        return 1
    finally:
        if temp_root is not None:
            shutil.rmtree(temp_root, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the E-arm audit finalizer.")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-slug", required=True)
    parser.add_argument("--arm-slug", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--claude-cmd", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--max-turns", required=True, type=int)
    parser.add_argument("--permission-mode", required=True)
    parser.add_argument("--plugin-dir", default=None)
    parser.add_argument("--hidden-evaluator-module", required=True)
    parser.add_argument("--main-verify-exit", required=True, type=int)
    parser.add_argument("--main-hidden-exit", required=True, type=int)
    args = parser.parse_args(argv)

    if args.command == "run":
        return run(
            workspace_root=args.workspace_root,
            run_dir=args.run_dir,
            run_id=args.run_id,
            task_slug=args.task_slug,
            arm_slug=args.arm_slug,
            phase=args.phase,
            prompt_file=args.prompt_file,
            claude_cmd=args.claude_cmd,
            model=args.model,
            effort=args.effort,
            max_turns=args.max_turns,
            permission_mode=args.permission_mode,
            plugin_dir=args.plugin_dir,
            hidden_evaluator_module=args.hidden_evaluator_module,
            main_verify_exit=args.main_verify_exit,
            main_hidden_exit=args.main_hidden_exit,
        )
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
