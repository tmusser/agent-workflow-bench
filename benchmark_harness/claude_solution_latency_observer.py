from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmark_harness.agent_turn_trace import (
    AgentTurnTraceRecorder,
    TRACE_FIDELITY_CHECKPOINT_ONLY,
    TRACE_FIDELITY_TURN_EVENT,
    TRACE_SOURCE_CLAUDE_MTIME_POLLING,
    TRACE_SOURCE_CLAUDE_STREAM_JSON,
)
from benchmark_harness import solution_latency_observer as shared

STREAM_JSON_MODE = shared.STREAM_JSON_MODE
MTIME_POLLING_MODE = shared.MTIME_POLLING_MODE

IGNORED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}

_STOP = object()


@dataclass
class CapturedClaudeWorkspace:
    checkpoint_index: int
    turn_index: int
    assistant_message_id: str | None
    source: str
    trigger: str
    wall_seconds: float
    permission_denials_delta: int
    fingerprint: str
    temp_root: Path
    snapshot_root: Path
    pause_seconds: float
    process_group_paused: bool


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


def _process_running(proc: subprocess.Popen[str]) -> bool:
    try:
        return proc.poll() is None
    except (AttributeError, OSError):
        return False


def _pause_process_group(proc: subprocess.Popen[str]) -> bool:
    if os.name != "posix" or not _process_running(proc):
        return False
    pid = getattr(proc, "pid", None)
    if not isinstance(pid, int):
        return False
    try:
        os.killpg(pid, signal.SIGSTOP)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    return True


def _resume_process_group(proc: subprocess.Popen[str]) -> None:
    if os.name != "posix":
        return
    pid = getattr(proc, "pid", None)
    if not isinstance(pid, int):
        return
    try:
        os.killpg(pid, signal.SIGCONT)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def capture_workspace(
    *,
    proc: subprocess.Popen[str],
    repo_root: Path,
    run_dir: Path,
    checkpoint_index: int,
    turn_index: int,
    assistant_message_id: str | None,
    source: str,
    trigger: str,
    wall_seconds: float,
    permission_denials_delta: int,
    previous_fingerprint: str | None,
) -> CapturedClaudeWorkspace | None:
    pause_started = time.monotonic()
    paused = _pause_process_group(proc)
    temp_root: Path | None = None
    try:
        fingerprint = workspace_fingerprint(repo_root)
        if fingerprint == previous_fingerprint:
            return None
        temp_root = Path(tempfile.mkdtemp(prefix="claude-first-green-", dir=run_dir))
        snapshot_root = temp_root / "repo"
        shutil.copytree(repo_root, snapshot_root, ignore=_snapshot_ignore)
    finally:
        if paused:
            _resume_process_group(proc)

    if temp_root is None:
        return None
    pause_seconds = round(time.monotonic() - pause_started, 6)
    capture = CapturedClaudeWorkspace(
        checkpoint_index=checkpoint_index,
        turn_index=turn_index,
        assistant_message_id=assistant_message_id,
        source=source,
        trigger=trigger,
        wall_seconds=wall_seconds,
        permission_denials_delta=max(permission_denials_delta, 0),
        fingerprint=fingerprint,
        temp_root=temp_root,
        snapshot_root=snapshot_root,
        pause_seconds=pause_seconds,
        process_group_paused=paused,
    )
    _write_json(
        run_dir / "solution_latency_checkpoints" / f"checkpoint_{checkpoint_index:04d}" / "capture.json",
        {
            "checkpoint_index": checkpoint_index,
            "turn_index": turn_index,
            "assistant_message_id": assistant_message_id,
            "source": source,
            "trigger": trigger,
            "wall_seconds": wall_seconds,
            "fingerprint": fingerprint,
            "process_group_paused": paused,
            "snapshot_pause_seconds": pause_seconds,
        },
    )
    return capture


def capture_final_workspace(
    *,
    repo_root: Path,
    run_dir: Path,
    checkpoint_index: int,
    turn_index: int,
    assistant_message_id: str | None,
    source: str,
    wall_seconds: float,
    previous_fingerprint: str | None,
) -> CapturedClaudeWorkspace | None:
    fingerprint = workspace_fingerprint(repo_root)
    if fingerprint == previous_fingerprint:
        return None
    temp_root = Path(tempfile.mkdtemp(prefix="claude-first-green-final-", dir=run_dir))
    snapshot_root = temp_root / "repo"
    shutil.copytree(repo_root, snapshot_root, ignore=_snapshot_ignore)
    return CapturedClaudeWorkspace(
        checkpoint_index=checkpoint_index,
        turn_index=max(turn_index, 1),
        assistant_message_id=assistant_message_id,
        source=source,
        trigger="final_workspace",
        wall_seconds=wall_seconds,
        permission_denials_delta=0,
        fingerprint=fingerprint,
        temp_root=temp_root,
        snapshot_root=snapshot_root,
        pause_seconds=0.0,
        process_group_paused=True,
    )


def evaluate_captures(
    *,
    captures: list[CapturedClaudeWorkspace],
    recorder: AgentTurnTraceRecorder,
    run_dir: Path,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    hidden_evaluator_module: str,
    benchmark_python: Path | None = None,
    environment: shared.BenchmarkPythonEnvironment | None = None,
) -> float:
    started = time.monotonic()
    benchmark_python = benchmark_python or shared.resolve_benchmark_python()
    for capture in captures:
        try:
            record = shared.evaluate_checkpoint_snapshot(
                repo_root=capture.snapshot_root,
                run_dir=run_dir,
                run_id=run_id,
                task_slug=task_slug,
                arm_slug=arm_slug,
                phase=phase,
                source=capture.source,
                checkpoint_index=capture.checkpoint_index,
                turn=capture.turn_index,
                assistant_message_id=capture.assistant_message_id,
                hidden_evaluator_module=hidden_evaluator_module,
                wall_seconds=capture.wall_seconds,
                permission_denials_delta=capture.permission_denials_delta,
                benchmark_python=benchmark_python,
                environment=environment,
            )
            recorder.record_checkpoint(
                checkpoint_index=capture.checkpoint_index,
                turn_index=capture.turn_index,
                provider_event_type="workspace_snapshot",
                assistant_message_id=capture.assistant_message_id,
                wall_seconds=capture.wall_seconds,
                verify_exit=record["verify_exit"],
                hidden_evaluator_exit=record["hidden_evaluator_exit"],
                functional_green=record["functional_green"],
                bench_ready_green=record["bench_ready_green"],
                permission_denials_delta=record["permission_denials_delta"],
                checkpoint_eval_errors=record["checkpoint_eval_errors"],
                benchmark_python=record["benchmark_python"],
                benchmark_python_realpath=record.get("benchmark_python_realpath"),
                benchmark_python_version=record["benchmark_python_version"],
                benchmark_python_prefix=record.get("benchmark_python_prefix"),
                benchmark_python_base_prefix=record.get("benchmark_python_base_prefix"),
                evaluation_environment_valid=record["evaluation_environment_valid"],
                evaluation_environment_errors=record["evaluation_environment_errors"],
                notes=[capture.trigger, "evaluated after Claude exited"],
            )
            _write_text(
                run_dir / "solution_latency_checkpoints" / f"checkpoint_{capture.checkpoint_index:04d}" / "trigger.txt",
                capture.trigger + "\n",
            )
        finally:
            shutil.rmtree(capture.temp_root, ignore_errors=True)
    return round(time.monotonic() - started, 6)


def _finish_observation(
    *,
    proc: subprocess.Popen[str],
    captures: list[CapturedClaudeWorkspace],
    recorder: AgentTurnTraceRecorder,
    run_dir: Path,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    hidden_evaluator_module: str,
    source: str,
    boundary_resolution: str,
    process_start_ns: int,
    process_end_ns: int,
    current_turn: int,
    distinct_states_skipped: int,
    complete_boundary_stream: bool,
    benchmark_python: Path,
    environment: shared.BenchmarkPythonEnvironment,
) -> int:
    process_wall_seconds = round((process_end_ns - process_start_ns) / 1_000_000_000, 6)
    evaluator_seconds = evaluate_captures(
        captures=captures,
        recorder=recorder,
        run_dir=run_dir,
        run_id=run_id,
        task_slug=task_slug,
        arm_slug=arm_slug,
        phase=phase,
        hidden_evaluator_module=hidden_evaluator_module,
        benchmark_python=benchmark_python,
        environment=environment,
    )
    exit_code = proc.returncode or 0
    recorder.record_run_result(
        provider_event_type="result",
        wall_seconds=process_wall_seconds,
        turn_index=current_turn or None,
        exit_code=exit_code,
        notes=["Claude process completed before snapshot evaluation"],
    )
    summary = recorder.finalize()

    live_captures = [item for item in captures if item.trigger != "final_workspace"]
    # A final-only snapshot can validate the terminal workspace, but it cannot
    # establish which live turn first became green. Exact stream coverage needs
    # at least one stable checkpoint captured while Claude was still running.
    stable_snapshots = bool(live_captures) and all(
        item.process_group_paused for item in live_captures
    )
    coverage_complete = (
        summary.get("evaluation_environment_valid", True) is True
        and
        bool(live_captures)
        and complete_boundary_stream
        and distinct_states_skipped == 0
        and stable_snapshots
    )
    summary.update(
        {
            "checkpoint_coverage_complete": coverage_complete,
            "stable_snapshot_coverage_complete": stable_snapshots,
            "checkpoint_evaluation_deferred": True,
            "checkpoint_boundary_resolution": boundary_resolution,
            "benchmark_python": str(benchmark_python),
            "native_observation_unit": "assistant_turn_and_file_changing_tool_result"
            if source == STREAM_JSON_MODE
            else "sampled_workspace_state",
            "workspace_states_observed": len(captures),
            "workspace_states_skipped": distinct_states_skipped,
            "checkpoint_snapshot_pause_seconds": round(sum(item.pause_seconds for item in captures), 6),
            "checkpoint_evaluator_seconds": evaluator_seconds,
            "claude_process_wall_seconds": process_wall_seconds,
            "solution_latency_observable": coverage_complete,
            "solution_latency_source": "claude_workspace_snapshots",
            "solution_latency_note": (
                "observed_from_complete_workspace_snapshots"
                if coverage_complete
                else "partial_workspace_snapshot_coverage"
            ),
        }
    )
    _write_json(run_dir / "agent_turn_trace_summary.json", summary)
    _write_json(
        run_dir / "claude_checkpoint_timing.json",
        {
            "process_start_ns": process_start_ns,
            "process_end_ns": process_end_ns,
            "claude_process_wall_seconds": process_wall_seconds,
            "snapshot_pause_seconds": round(sum(item.pause_seconds for item in captures), 6),
            "evaluator_wall_seconds": evaluator_seconds,
            "workspace_states_observed": len(captures),
            "workspace_states_skipped": distinct_states_skipped,
            "checkpoint_coverage_complete": coverage_complete,
            "stable_snapshot_coverage_complete": stable_snapshots,
            "checkpoint_boundary_resolution": boundary_resolution,
            "benchmark_python": str(benchmark_python),
            "benchmark_python_version": summary.get("benchmark_python_version"),
            "evaluation_environment_valid": summary.get("evaluation_environment_valid"),
            "evaluation_environment_errors": summary.get("evaluation_environment_errors", []),
        },
    )
    _write_text(run_dir / "claude_exit_code.txt", f"{exit_code}\n")
    return exit_code


def _build_claude_command(
    *,
    claude_cmd: str,
    prompt_text: str,
    model: str,
    effort: str,
    max_turns: int,
    permission_mode: str,
    plugin_dir: str | None,
    output_format: str,
    include_partial_messages: bool,
) -> list[str]:
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
            *shared._claude_permission_args(permission_mode),
            "--output-format",
            output_format,
        ]
    )
    if include_partial_messages:
        command.extend(["--verbose", "--include-partial-messages"])
    command.append(prompt_text)
    return command


def _run_stream_json_observer(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    prompt_text: str,
    claude_cmd: str,
    model: str,
    effort: str,
    max_turns: int,
    permission_mode: str,
    plugin_dir: str | None,
    hidden_evaluator_module: str,
    max_checkpoints: int,
    benchmark_python: Path,
    environment: shared.BenchmarkPythonEnvironment,
) -> int:
    stdout_path = run_dir / "claude_stdout.txt"
    stderr_path = run_dir / "claude_stderr.txt"
    events_path = run_dir / "claude_events.jsonl"
    run_dir.mkdir(parents=True, exist_ok=True)
    for path in (stdout_path, stderr_path, events_path, run_dir / "agent_turn_trace.jsonl"):
        _write_text(path, "")

    command = _build_claude_command(
        claude_cmd=claude_cmd,
        prompt_text=prompt_text,
        model=model,
        effort=effort,
        max_turns=max_turns,
        permission_mode=permission_mode,
        plugin_dir=plugin_dir,
        output_format="stream-json",
        include_partial_messages=True,
    )
    process_start_ns = time.time_ns()
    process_started = time.monotonic()
    proc = subprocess.Popen(
        command,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=os.name == "posix",
    )

    stdout_queue: queue.Queue[str | object] = queue.Queue()

    def pump_stdout() -> None:
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                stdout_queue.put(line)
        finally:
            stdout_queue.put(_STOP)

    def pump_stderr() -> None:
        assert proc.stderr is not None
        with stderr_path.open("w", encoding="utf-8") as handle:
            for line in proc.stderr:
                handle.write(line)
                handle.flush()

    stdout_thread = threading.Thread(target=pump_stdout, name="claude-stdout-pump", daemon=True)
    stderr_thread = threading.Thread(target=pump_stderr, name="claude-stderr-pump", daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    recorder = AgentTurnTraceRecorder(
        run_id=run_id,
        task_slug=task_slug,
        arm_slug=arm_slug,
        phase=phase,
        provider="claude",
        runner="claude-cli",
        trace_source=TRACE_SOURCE_CLAUDE_STREAM_JSON,
        trace_fidelity=TRACE_FIDELITY_TURN_EVENT,
        repo_root=repo_root,
        jsonl_path=run_dir / "agent_turn_trace.jsonl",
        summary_path=run_dir / "agent_turn_trace_summary.json",
    )

    captures: list[CapturedClaudeWorkspace] = []
    previous_fingerprint: str | None = None
    distinct_states_skipped = 0
    current_message_id: str | None = None
    current_turn = 0
    current_turn_had_file_change = False
    current_turn_completed = False
    tool_use_to_name: dict[str, str] = {}
    tool_use_to_file_change: dict[str, bool] = {}
    unresolved_file_change_tool_uses: set[str] = set()
    permission_denials_total = 0
    last_capture_permission_denials_total = 0

    def capture_current_state(trigger: str) -> None:
        nonlocal previous_fingerprint, distinct_states_skipped, last_capture_permission_denials_total
        if current_turn <= 0 or not current_turn_had_file_change:
            return
        if len(captures) >= max(max_checkpoints - 1, 0):
            fingerprint = workspace_fingerprint(repo_root)
            if fingerprint != previous_fingerprint:
                distinct_states_skipped += 1
                previous_fingerprint = fingerprint
            return
        capture = capture_workspace(
            proc=proc,
            repo_root=repo_root,
            run_dir=run_dir,
            checkpoint_index=len(captures) + 1,
            turn_index=current_turn,
            assistant_message_id=current_message_id,
            source=STREAM_JSON_MODE,
            trigger=trigger,
            wall_seconds=round(time.monotonic() - process_started, 3),
            permission_denials_delta=max(
                permission_denials_total - last_capture_permission_denials_total,
                0,
            ),
            previous_fingerprint=previous_fingerprint,
        )
        if capture is None:
            return
        captures.append(capture)
        previous_fingerprint = capture.fingerprint
        last_capture_permission_denials_total = permission_denials_total
        recorder.record_file_change_observed(
            turn_index=current_turn,
            provider_event_type="workspace_snapshot",
            checkpoint_index=capture.checkpoint_index,
            message_id=current_message_id,
            wall_seconds=capture.wall_seconds,
            notes=[trigger],
        )

    def complete_current_turn(trigger: str) -> None:
        nonlocal current_turn_completed
        if current_message_id is None or current_turn_completed:
            return
        recorder.record_turn_completed(
            turn_index=current_turn,
            provider_event_type=trigger,
            message_id=current_message_id,
            wall_seconds=round(time.monotonic() - process_started, 3),
            notes=[trigger],
        )
        current_turn_completed = True

    def handle_event(event: dict[str, Any]) -> None:
        nonlocal current_message_id, current_turn, current_turn_had_file_change, current_turn_completed, permission_denials_total
        event_type = str(event.get("type") or "").lower()
        total = shared._event_permission_denials_total(event)
        if total is not None:
            permission_denials_total = total

        if event_type == "assistant":
            message_id = shared._event_message_id(event)
            if message_id and message_id != current_message_id:
                # Do not snapshot at the next assistant boundary. By the time the
                # observer consumes that event, the next tool may already be running,
                # which can misattribute the next turn's workspace to the prior turn.
                # Completed file-changing tool results are the exact stream boundary.
                complete_current_turn("assistant_boundary")
                current_message_id = message_id
                current_turn += 1
                current_turn_had_file_change = False
                current_turn_completed = False
                recorder.record_turn_started(
                    turn_index=current_turn,
                    provider_event_type="assistant",
                    message_id=current_message_id,
                    wall_seconds=round(time.monotonic() - process_started, 3),
                )
                recorder.record_assistant_message(
                    turn_index=current_turn,
                    provider_event_type="assistant",
                    message_id=current_message_id,
                    wall_seconds=round(time.monotonic() - process_started, 3),
                )
            for block in shared._event_content(event):
                if block.get("type") != "tool_use":
                    continue
                tool_use_id = shared._tool_use_id_from_block(block)
                tool_name = shared._tool_name_from_content_block(block)
                if tool_use_id and tool_name:
                    tool_use_to_name[tool_use_id] = tool_name
                    tool_use_to_file_change[tool_use_id] = shared._is_file_changing_tool(tool_name)
                    if tool_use_to_file_change[tool_use_id]:
                        unresolved_file_change_tool_uses.add(tool_use_id)
                    recorder.record_tool_use(
                        turn_index=current_turn or None,
                        provider_event_type="assistant",
                        tool_use_id=tool_use_id,
                        tool_name=tool_name,
                        message_id=current_message_id,
                        wall_seconds=round(time.monotonic() - process_started, 3),
                        file_changing_tool=tool_use_to_file_change[tool_use_id],
                    )
            return

        if event_type == "user":
            file_change_detected = False
            for tool_use_id in shared._event_tool_result_ids(event):
                is_file_change = bool(tool_use_to_file_change.get(tool_use_id))
                if is_file_change:
                    unresolved_file_change_tool_uses.discard(tool_use_id)
                file_change_detected = file_change_detected or is_file_change
                recorder.record_tool_result(
                    turn_index=current_turn or None,
                    provider_event_type="user",
                    tool_use_id=tool_use_id,
                    tool_name=tool_use_to_name.get(tool_use_id),
                    message_id=current_message_id,
                    wall_seconds=round(time.monotonic() - process_started, 3),
                    file_changing_tool=is_file_change,
                )
            if file_change_detected:
                current_turn_had_file_change = True
                capture_current_state("file_changing_tool_result")
            return

        if event_type == "result":
            capture_current_state("final_result")
            complete_current_turn("result")

    while True:
        item = stdout_queue.get()
        if item is _STOP:
            break
        stdout_line = str(item)
        with stdout_path.open("a", encoding="utf-8") as handle:
            handle.write(stdout_line)
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(stdout_line)
        try:
            parsed = json.loads(stdout_line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            handle_event(parsed)

    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    proc.wait()
    process_end_ns = time.time_ns()
    capture_current_state("stream_end")
    complete_current_turn("stream_end")

    final_capture = capture_final_workspace(
        repo_root=repo_root,
        run_dir=run_dir,
        checkpoint_index=len(captures) + 1,
        turn_index=current_turn,
        assistant_message_id=current_message_id,
        source=STREAM_JSON_MODE,
        wall_seconds=round((process_end_ns - process_start_ns) / 1_000_000_000, 3),
        previous_fingerprint=previous_fingerprint,
    )
    if final_capture is not None:
        if len(captures) < max_checkpoints:
            captures.append(final_capture)
        else:
            shutil.rmtree(final_capture.temp_root, ignore_errors=True)
            distinct_states_skipped += 1

    return _finish_observation(
        proc=proc,
        captures=captures,
        recorder=recorder,
        run_dir=run_dir,
        run_id=run_id,
        task_slug=task_slug,
        arm_slug=arm_slug,
        phase=phase,
        hidden_evaluator_module=hidden_evaluator_module,
        source=STREAM_JSON_MODE,
        boundary_resolution="file_changing_tool_result_then_process_group_pause",
        process_start_ns=process_start_ns,
        process_end_ns=process_end_ns,
        current_turn=current_turn,
        distinct_states_skipped=distinct_states_skipped,
        complete_boundary_stream=not unresolved_file_change_tool_uses,
        benchmark_python=benchmark_python,
        environment=environment,
    )


def _stream_to_file(stream: Any, output_path: Path) -> None:
    if stream is None:
        return
    with output_path.open("a", encoding="utf-8") as handle:
        for line in stream:
            handle.write(line)
            handle.flush()


def _run_mtime_polling_observer(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    prompt_text: str,
    claude_cmd: str,
    model: str,
    effort: str,
    max_turns: int,
    permission_mode: str,
    plugin_dir: str | None,
    hidden_evaluator_module: str,
    max_checkpoints: int,
    benchmark_python: Path,
    environment: shared.BenchmarkPythonEnvironment,
) -> int:
    stdout_path = run_dir / "claude_stdout.txt"
    stderr_path = run_dir / "claude_stderr.txt"
    run_dir.mkdir(parents=True, exist_ok=True)
    for path in (stdout_path, stderr_path, run_dir / "agent_turn_trace.jsonl"):
        _write_text(path, "")

    command = _build_claude_command(
        claude_cmd=claude_cmd,
        prompt_text=prompt_text,
        model=model,
        effort=effort,
        max_turns=max_turns,
        permission_mode=permission_mode,
        plugin_dir=plugin_dir,
        output_format="json",
        include_partial_messages=False,
    )
    process_start_ns = time.time_ns()
    process_started = time.monotonic()
    proc = subprocess.Popen(
        command,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=os.name == "posix",
    )
    stdout_thread = threading.Thread(
        target=lambda: _stream_to_file(proc.stdout, stdout_path),
        name="claude-stdout-pump",
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=lambda: _stream_to_file(proc.stderr, stderr_path),
        name="claude-stderr-pump",
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    recorder = AgentTurnTraceRecorder(
        run_id=run_id,
        task_slug=task_slug,
        arm_slug=arm_slug,
        phase=phase,
        provider="claude",
        runner="claude-cli",
        trace_source=TRACE_SOURCE_CLAUDE_MTIME_POLLING,
        trace_fidelity=TRACE_FIDELITY_CHECKPOINT_ONLY,
        repo_root=repo_root,
        jsonl_path=run_dir / "agent_turn_trace.jsonl",
        summary_path=run_dir / "agent_turn_trace_summary.json",
    )

    captures: list[CapturedClaudeWorkspace] = []
    previous_fingerprint = workspace_fingerprint(repo_root)
    distinct_states_skipped = 0
    while proc.poll() is None:
        time.sleep(0.5)
        current_fingerprint = workspace_fingerprint(repo_root)
        if current_fingerprint == previous_fingerprint:
            continue
        if len(captures) >= max(max_checkpoints - 1, 0):
            distinct_states_skipped += 1
            previous_fingerprint = current_fingerprint
            continue
        checkpoint_index = len(captures) + 1
        capture = capture_workspace(
            proc=proc,
            repo_root=repo_root,
            run_dir=run_dir,
            checkpoint_index=checkpoint_index,
            turn_index=checkpoint_index,
            assistant_message_id=None,
            source=MTIME_POLLING_MODE,
            trigger="mtime_polling_change",
            wall_seconds=round(time.monotonic() - process_started, 3),
            permission_denials_delta=0,
            previous_fingerprint=previous_fingerprint,
        )
        if capture is None:
            continue
        captures.append(capture)
        previous_fingerprint = capture.fingerprint
        recorder.record_file_change_observed(
            turn_index=checkpoint_index,
            provider_event_type="mtime_polling",
            checkpoint_index=checkpoint_index,
            wall_seconds=capture.wall_seconds,
            notes=["sampled workspace change"],
        )
        recorder.record_turn_completed(
            turn_index=checkpoint_index,
            provider_event_type="mtime_polling",
            wall_seconds=capture.wall_seconds,
            notes=["synthetic checkpoint index; not a native Claude turn"],
        )

    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    proc.wait()
    process_end_ns = time.time_ns()

    final_capture = capture_final_workspace(
        repo_root=repo_root,
        run_dir=run_dir,
        checkpoint_index=len(captures) + 1,
        turn_index=len(captures) + 1,
        assistant_message_id=None,
        source=MTIME_POLLING_MODE,
        wall_seconds=round((process_end_ns - process_start_ns) / 1_000_000_000, 3),
        previous_fingerprint=previous_fingerprint,
    )
    if final_capture is not None:
        if len(captures) < max_checkpoints:
            captures.append(final_capture)
        else:
            shutil.rmtree(final_capture.temp_root, ignore_errors=True)
            distinct_states_skipped += 1

    return _finish_observation(
        proc=proc,
        captures=captures,
        recorder=recorder,
        run_dir=run_dir,
        run_id=run_id,
        task_slug=task_slug,
        arm_slug=arm_slug,
        phase=phase,
        hidden_evaluator_module=hidden_evaluator_module,
        source=MTIME_POLLING_MODE,
        boundary_resolution="sampled_workspace_change_then_process_group_pause",
        process_start_ns=process_start_ns,
        process_end_ns=process_end_ns,
        current_turn=len(captures),
        distinct_states_skipped=distinct_states_skipped,
        complete_boundary_stream=False,
        benchmark_python=benchmark_python,
        environment=environment,
    )


def run(
    *,
    repo_root: Path,
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
    mode: str,
    max_checkpoints: int,
    benchmark_python: str | Path | None = None,
) -> int:
    prompt_text = prompt_file.read_text(encoding="utf-8")
    run_dir.mkdir(parents=True, exist_ok=True)
    selected_python = shared.resolve_benchmark_python(benchmark_python)
    environment = shared.validate_benchmark_python(selected_python)
    if not environment.valid:
        _write_text(
            run_dir / "solution_latency_observer_error.txt",
            "evaluation environment invalid; agent was not started\n" + "\n".join(environment.errors) + "\n",
        )
        return 2
    try:
        if mode == STREAM_JSON_MODE:
            return _run_stream_json_observer(
                repo_root=repo_root,
                run_dir=run_dir,
                run_id=run_id,
                task_slug=task_slug,
                arm_slug=arm_slug,
                phase=phase,
                prompt_text=prompt_text,
                claude_cmd=claude_cmd,
                model=model,
                effort=effort,
                max_turns=max_turns,
                permission_mode=permission_mode,
                plugin_dir=plugin_dir,
                hidden_evaluator_module=hidden_evaluator_module,
                max_checkpoints=max_checkpoints,
                benchmark_python=selected_python,
                environment=environment,
            )
        if mode == MTIME_POLLING_MODE:
            return _run_mtime_polling_observer(
                repo_root=repo_root,
                run_dir=run_dir,
                run_id=run_id,
                task_slug=task_slug,
                arm_slug=arm_slug,
                phase=phase,
                prompt_text=prompt_text,
                claude_cmd=claude_cmd,
                model=model,
                effort=effort,
                max_turns=max_turns,
                permission_mode=permission_mode,
                plugin_dir=plugin_dir,
                hidden_evaluator_module=hidden_evaluator_module,
                max_checkpoints=max_checkpoints,
                benchmark_python=selected_python,
                environment=environment,
            )
        raise ValueError(f"unknown observation mode: {mode}")
    except Exception as exc:  # pragma: no cover - best-effort error handling
        _write_text(run_dir / "solution_latency_observer_error.txt", f"{exc.__class__.__name__}: {exc}\n")
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Claude with stable deferred solution-latency observation.")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--repo-root", required=True, type=Path)
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
    parser.add_argument("--mode", required=True, choices=[STREAM_JSON_MODE, MTIME_POLLING_MODE])
    parser.add_argument("--max-checkpoints", type=int, default=32)
    parser.add_argument("--benchmark-python", default=None)
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
        claude_cmd=args.claude_cmd,
        model=args.model,
        effort=args.effort,
        max_turns=args.max_turns,
        permission_mode=args.permission_mode,
        plugin_dir=args.plugin_dir,
        hidden_evaluator_module=args.hidden_evaluator_module,
        mode=args.mode,
        max_checkpoints=args.max_checkpoints,
        benchmark_python=args.benchmark_python,
    )


if __name__ == "__main__":
    raise SystemExit(main())
