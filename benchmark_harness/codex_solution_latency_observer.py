from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from benchmark_harness.agent_turn_trace import (
    AgentTurnTraceRecorder,
    TRACE_FIDELITY_TURN_EVENT,
    TRACE_SOURCE_CODEX_JSONL,
    _codex_command_category,
    _codex_item_type,
    _extract_item_payload,
    parse_json_records,
    process_codex_record,
)
from benchmark_harness.solution_latency_observer import evaluate_checkpoint_snapshot

IGNORED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}


@dataclass
class CapturedWorkspace:
    checkpoint_index: int
    provider_item_index: int
    trigger: str
    wall_seconds: float
    fingerprint: str
    temp_root: Path
    snapshot_root: Path
    pause_seconds: float


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _snapshot_ignore(_: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED_DIRS or name == ".DS_Store"}


def workspace_fingerprint(repo_root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(repo_root.rglob("*")):
        relative = path.relative_to(repo_root)
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        if not path.is_file():
            continue
        digest.update(str(relative).replace(os.sep, "/").encode("utf-8"))
        digest.update(b"\0")
        try:
            with path.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
        except OSError:
            digest.update(b"<unreadable>")
        digest.update(b"\0")
    return digest.hexdigest()


def _pause_process_group(proc: subprocess.Popen[str]) -> bool:
    if os.name != "posix" or proc.poll() is not None:
        return False
    try:
        os.killpg(proc.pid, signal.SIGSTOP)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    return True


def _resume_process_group(proc: subprocess.Popen[str]) -> None:
    if os.name != "posix":
        return
    try:
        os.killpg(proc.pid, signal.SIGCONT)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def capture_workspace(
    *,
    proc: subprocess.Popen[str],
    repo_root: Path,
    run_dir: Path,
    checkpoint_index: int,
    provider_item_index: int,
    trigger: str,
    wall_seconds: float,
    previous_fingerprint: str | None,
) -> CapturedWorkspace | None:
    pause_started = time.monotonic()
    paused = _pause_process_group(proc)
    temp_root: Path | None = None
    try:
        fingerprint = workspace_fingerprint(repo_root)
        if fingerprint == previous_fingerprint:
            return None
        temp_root = Path(tempfile.mkdtemp(prefix="codex-first-green-", dir=run_dir))
        snapshot_root = temp_root / "repo"
        shutil.copytree(repo_root, snapshot_root, ignore=_snapshot_ignore)
    finally:
        if paused:
            _resume_process_group(proc)
    pause_seconds = round(time.monotonic() - pause_started, 6)
    if temp_root is None:
        return None
    capture = CapturedWorkspace(
        checkpoint_index=checkpoint_index,
        provider_item_index=provider_item_index,
        trigger=trigger,
        wall_seconds=wall_seconds,
        fingerprint=fingerprint,
        temp_root=temp_root,
        snapshot_root=snapshot_root,
        pause_seconds=pause_seconds,
    )
    _write_json(
        run_dir / "solution_latency_checkpoints" / f"checkpoint_{checkpoint_index:04d}" / "capture.json",
        {
            "checkpoint_index": checkpoint_index,
            "provider_item_index": provider_item_index,
            "trigger": trigger,
            "wall_seconds": wall_seconds,
            "fingerprint": fingerprint,
            "process_group_paused": paused,
            "snapshot_pause_seconds": pause_seconds,
        },
    )
    return capture


def _provider_item_index(rows: list[dict[str, Any]]) -> int | None:
    for row in reversed(rows):
        if row.get("event_kind") != "provider_item":
            continue
        value = row.get("provider_item_index")
        if isinstance(value, int):
            return value
    return None


def _candidate_trigger(record: dict[str, Any]) -> str | None:
    event_type = str(record.get("type") or record.get("event_type") or "").lower().replace(".", "_").replace("-", "_")
    if event_type != "item_completed":
        return None
    item = _extract_item_payload(record)
    if item is None:
        return None
    item_type = _codex_item_type(item)
    if item_type == "file_change":
        return "file_change_completed"
    if item_type == "command_execution":
        category = _codex_command_category(item) or "other"
        return f"command_completed:{category}"
    return None


def _load_command(path: Path) -> list[str]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise ValueError("command JSON must be a non-empty list of strings")
    return value


def _build_command(command: list[str], prompt_file: Path, prompt_mode: str) -> tuple[list[str], str | None]:
    prompt_text = prompt_file.read_text(encoding="utf-8")
    if prompt_mode == "arg":
        return [*command, prompt_text], None
    if prompt_mode == "stdin":
        return command, prompt_text
    if prompt_mode == "file":
        return [*command, str(prompt_file.resolve())], None
    raise ValueError(f"unknown prompt mode: {prompt_mode}")


def evaluate_captures(
    *,
    captures: list[CapturedWorkspace],
    recorder: AgentTurnTraceRecorder,
    run_dir: Path,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    hidden_evaluator_module: str,
    verify_runner: Callable[[Path, Path], int] | None = None,
    hidden_runner: Callable[[Path, Path], int] | None = None,
) -> float:
    started = time.monotonic()
    for capture in captures:
        try:
            record = evaluate_checkpoint_snapshot(
                repo_root=capture.snapshot_root,
                run_dir=run_dir,
                run_id=run_id,
                task_slug=task_slug,
                arm_slug=arm_slug,
                phase=phase,
                source="codex_workspace_snapshot",
                checkpoint_index=capture.checkpoint_index,
                turn=1,
                provider_item_index=capture.provider_item_index,
                assistant_message_id=None,
                hidden_evaluator_module=hidden_evaluator_module,
                wall_seconds=capture.wall_seconds,
                verify_runner=verify_runner,
                hidden_runner=hidden_runner,
            )
            recorder.record_checkpoint(
                checkpoint_index=capture.checkpoint_index,
                turn_index=1,
                provider_item_index=capture.provider_item_index,
                provider_event_type="workspace_snapshot",
                assistant_message_id=None,
                wall_seconds=capture.wall_seconds,
                verify_exit=record["verify_exit"],
                hidden_evaluator_exit=record["hidden_evaluator_exit"],
                functional_green=record["functional_green"],
                bench_ready_green=record["bench_ready_green"],
                permission_denials_delta=0,
                checkpoint_eval_errors=record["checkpoint_eval_errors"],
                notes=[capture.trigger, "evaluated after Codex exited"],
            )
            _write_text(
                run_dir / "solution_latency_checkpoints" / f"checkpoint_{capture.checkpoint_index:04d}" / "trigger.txt",
                capture.trigger + "\n",
            )
        finally:
            shutil.rmtree(capture.temp_root, ignore_errors=True)
    return round(time.monotonic() - started, 6)


def run(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    prompt_file: Path,
    prompt_mode: str,
    command_json: Path,
    hidden_evaluator_module: str,
    max_checkpoints: int,
) -> int:
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = run_dir / "codex_stdout.txt"
    stderr_path = run_dir / "codex_stderr.txt"
    exit_path = run_dir / "codex_exit_code.txt"
    trace_path = run_dir / "agent_turn_trace.jsonl"
    summary_path = run_dir / "agent_turn_trace_summary.json"
    for path in (stdout_path, stderr_path, trace_path):
        _write_text(path, "")

    command, stdin_text = _build_command(_load_command(command_json), prompt_file, prompt_mode)
    process_start_ns = time.time_ns()
    process_started = time.monotonic()
    proc = subprocess.Popen(
        command,
        cwd=repo_root,
        stdin=subprocess.PIPE if stdin_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=os.name == "posix",
    )
    if stdin_text is not None and proc.stdin is not None:
        proc.stdin.write(stdin_text)
        proc.stdin.close()

    def pump_stderr() -> None:
        assert proc.stderr is not None
        with stderr_path.open("w", encoding="utf-8") as handle:
            for line in proc.stderr:
                handle.write(line)
                handle.flush()

    stderr_thread = threading.Thread(target=pump_stderr, name="codex-stderr-pump", daemon=True)
    stderr_thread.start()

    recorder = AgentTurnTraceRecorder(
        run_id=run_id,
        task_slug=task_slug,
        arm_slug=arm_slug,
        phase=phase,
        provider="codex",
        runner="codex-cli",
        trace_source=TRACE_SOURCE_CODEX_JSONL,
        trace_fidelity=TRACE_FIDELITY_TURN_EVENT,
        repo_root=repo_root,
        jsonl_path=trace_path,
        summary_path=summary_path,
    )

    captures: list[CapturedWorkspace] = []
    current_turn: int | None = None
    previous_fingerprint: str | None = None
    distinct_states_skipped = 0
    last_provider_item_index = 0
    max_intermediate = max(max_checkpoints - 1, 0)

    assert proc.stdout is not None
    with stdout_path.open("w", encoding="utf-8") as stdout_handle:
        for line in proc.stdout:
            stdout_handle.write(line)
            stdout_handle.flush()
            for record in parse_json_records(line):
                before = len(recorder.rows)
                current_turn = process_codex_record(recorder, record, current_turn_index=current_turn)
                new_rows = recorder.rows[before:]
                item_index = _provider_item_index(new_rows)
                if item_index is not None:
                    last_provider_item_index = max(last_provider_item_index, item_index)
                trigger = _candidate_trigger(record)
                if trigger is None or item_index is None:
                    continue
                if len(captures) >= max_intermediate:
                    current_fingerprint = workspace_fingerprint(repo_root)
                    if current_fingerprint != previous_fingerprint:
                        distinct_states_skipped += 1
                        previous_fingerprint = current_fingerprint
                    continue
                capture = capture_workspace(
                    proc=proc,
                    repo_root=repo_root,
                    run_dir=run_dir,
                    checkpoint_index=len(captures) + 1,
                    provider_item_index=item_index,
                    trigger=trigger,
                    wall_seconds=round(time.monotonic() - process_started, 3),
                    previous_fingerprint=previous_fingerprint,
                )
                if capture is not None:
                    captures.append(capture)
                    previous_fingerprint = capture.fingerprint

    proc.wait()
    stderr_thread.join(timeout=5)
    process_end_ns = time.time_ns()
    process_wall_seconds = round((process_end_ns - process_start_ns) / 1_000_000_000, 6)

    final_fingerprint = workspace_fingerprint(repo_root)
    if not captures or final_fingerprint != captures[-1].fingerprint:
        if len(captures) < max_checkpoints:
            temp_root = Path(tempfile.mkdtemp(prefix="codex-first-green-final-", dir=run_dir))
            snapshot_root = temp_root / "repo"
            shutil.copytree(repo_root, snapshot_root, ignore=_snapshot_ignore)
            final_item_index = max(last_provider_item_index, 1)
            capture = CapturedWorkspace(
                checkpoint_index=len(captures) + 1,
                provider_item_index=final_item_index,
                trigger="final_workspace",
                wall_seconds=process_wall_seconds,
                fingerprint=final_fingerprint,
                temp_root=temp_root,
                snapshot_root=snapshot_root,
                pause_seconds=0.0,
            )
            captures.append(capture)
        else:
            distinct_states_skipped += 1

    evaluator_seconds = evaluate_captures(
        captures=captures,
        recorder=recorder,
        run_dir=run_dir,
        run_id=run_id,
        task_slug=task_slug,
        arm_slug=arm_slug,
        phase=phase,
        hidden_evaluator_module=hidden_evaluator_module,
    )
    exit_code = proc.returncode or 0
    recorder.record_run_result(
        provider_event_type="result",
        wall_seconds=process_wall_seconds,
        turn_index=current_turn,
        exit_code=exit_code,
        notes=["Codex process completed before snapshot evaluation"],
    )
    summary = recorder.finalize()
    coverage_complete = distinct_states_skipped == 0
    summary.update(
        {
            "checkpoint_coverage_complete": coverage_complete,
            "workspace_states_observed": len(captures),
            "workspace_states_skipped": distinct_states_skipped,
            "checkpoint_snapshot_pause_seconds": round(sum(item.pause_seconds for item in captures), 6),
            "checkpoint_evaluator_seconds": evaluator_seconds,
            "codex_process_wall_seconds": process_wall_seconds,
        }
    )
    if captures:
        summary["solution_latency_observable"] = coverage_complete
        summary["solution_latency_source"] = "codex_workspace_snapshots"
        summary["solution_latency_note"] = (
            "observed_from_complete_workspace_snapshots" if coverage_complete else "partial_workspace_snapshot_coverage"
        )
    _write_json(summary_path, summary)
    _write_json(
        run_dir / "codex_checkpoint_timing.json",
        {
            "process_start_ns": process_start_ns,
            "process_end_ns": process_end_ns,
            "codex_process_wall_seconds": process_wall_seconds,
            "snapshot_pause_seconds": round(sum(item.pause_seconds for item in captures), 6),
            "evaluator_wall_seconds": evaluator_seconds,
            "workspace_states_observed": len(captures),
            "workspace_states_skipped": distinct_states_skipped,
            "checkpoint_coverage_complete": coverage_complete,
        },
    )
    _write_text(exit_path, f"{exit_code}\n")
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Codex while capturing evaluator-ready workspace states.")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-slug", required=True)
    parser.add_argument("--arm-slug", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--prompt-mode", required=True, choices=["arg", "stdin", "file"])
    parser.add_argument("--command-json", required=True, type=Path)
    parser.add_argument("--hidden-evaluator-module", required=True)
    parser.add_argument("--max-checkpoints", type=int, default=32)
    args = parser.parse_args(argv)
    if args.max_checkpoints < 1:
        parser.error("--max-checkpoints must be at least 1")
    return run(
        repo_root=args.repo_root,
        run_dir=args.run_dir,
        run_id=args.run_id,
        task_slug=args.task_slug,
        arm_slug=args.arm_slug,
        phase=args.phase,
        prompt_file=args.prompt_file,
        prompt_mode=args.prompt_mode,
        command_json=args.command_json,
        hidden_evaluator_module=args.hidden_evaluator_module,
        max_checkpoints=args.max_checkpoints,
    )


if __name__ == "__main__":
    raise SystemExit(main())
