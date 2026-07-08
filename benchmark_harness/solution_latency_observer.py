from __future__ import annotations

import argparse
import json
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

from benchmark_harness.agent_turn_trace import (
    AgentTurnTraceRecorder,
    TRACE_FIDELITY_CHECKPOINT_ONLY,
    TRACE_FIDELITY_TURN_EVENT,
    TRACE_SOURCE_CLAUDE_MTIME_POLLING,
    TRACE_SOURCE_CLAUDE_STREAM_JSON,
)
from benchmark_harness.validate_skill_runtime_proof import validate as validate_skill_runtime_proof

STREAM_JSON_MODE = "stream_json"
MTIME_POLLING_MODE = "mtime_polling"

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FILE_CHANGING_TOOLS = {
    "Bash",
    "Create",
    "Delete",
    "Edit",
    "Move",
    "MultiEdit",
    "NotebookEdit",
    "Rename",
    "Replace",
    "Write",
}

_STOP = object()


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


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _claude_permission_args(permission_mode: str) -> list[str]:
    if permission_mode in {"dangerously-skip-permissions", "skip"}:
        return ["--dangerously-skip-permissions"]
    return ["--permission-mode", permission_mode]


def supports_stream_json(claude_cmd: str) -> bool:
    try:
        proc = subprocess.run(
            [claude_cmd, "-p", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    help_text = f"{proc.stdout}\n{proc.stderr}".lower()
    return "stream-json" in help_text and "output-format" in help_text


def _snapshot_ignore(_: str, names: list[str]) -> set[str]:
    ignored = {
        ".DS_Store",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "node_modules",
    }
    return {name for name in names if name in ignored}


def _snapshot_repo(repo_root: Path) -> tuple[Path, Path]:
    temp_root = Path(tempfile.mkdtemp(prefix="solution-latency-snapshot-"))
    snapshot_root = temp_root / repo_root.name
    shutil.copytree(repo_root, snapshot_root, ignore=_snapshot_ignore)
    return temp_root, snapshot_root


def _run_command(command: list[str], *, cwd: Path, output_path: Path) -> int:
    proc = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    _write_text(output_path, f"{proc.stdout or ''}{proc.stderr or ''}")
    return proc.returncode


def _default_verify_runner(snapshot_root: Path, output_path: Path) -> int:
    return _run_command(["bash", "./VERIFY.sh"], cwd=snapshot_root, output_path=output_path)


def _default_hidden_runner(hidden_evaluator_module: str) -> Callable[[Path, Path], int]:
    def _runner(snapshot_root: Path, output_path: Path) -> int:
        command = [
            sys.executable,
            "-m",
            hidden_evaluator_module,
            "--repo",
            str(snapshot_root),
        ]
        return _run_command(command, cwd=PROJECT_ROOT, output_path=output_path)

    return _runner


def _validate_skill_runtime(snapshot_root: Path) -> tuple[bool, list[str]]:
    proof_path = snapshot_root / "SKILL_RUNTIME_PROOF.md"
    if not proof_path.exists() or not proof_path.is_file():
        return False, ["missing SKILL_RUNTIME_PROOF.md"]
    try:
        issues = validate_skill_runtime_proof(proof_path)
    except Exception as exc:  # pragma: no cover - defensive guard
        return False, [f"{exc.__class__.__name__}: {exc}"]
    return not issues, issues


def is_bench_ready_green(arm_slug: str, snapshot_root: Path, functional_green: bool) -> tuple[bool, list[str]]:
    if not functional_green:
        return False, []

    if arm_slug == "A-baseline":
        return True, []

    if arm_slug == "E-ai-engineering-skills":
        issues: list[str] = []
        if not (snapshot_root / "VERIFY.md").exists():
            issues.append("missing VERIFY.md")
        skill_ready, skill_issues = _validate_skill_runtime(snapshot_root)
        if not skill_ready:
            issues.extend(skill_issues)
        return not issues, issues

    return functional_green, []


def _checkpoint_record(
    *,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    source: str,
    checkpoint_index: int,
    turn: int,
    assistant_message_id: str | None,
    wall_seconds: float,
    verify_exit: int,
    hidden_exit: int,
    functional_green: bool,
    bench_ready_green: bool,
    permission_denials_delta: int,
    checkpoint_eval_errors: list[str],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "task_slug": task_slug,
        "arm_slug": arm_slug,
        "phase": phase,
        "source": source,
        "checkpoint_index": checkpoint_index,
        "turn": turn,
        "assistant_message_id": assistant_message_id,
        "wall_seconds": wall_seconds,
        "verify_exit": verify_exit,
        "hidden_evaluator_exit": hidden_exit,
        "functional_green": functional_green,
        "bench_ready_green": bench_ready_green,
        "permission_denials_delta": max(permission_denials_delta, 0),
        "checkpoint_eval_errors": checkpoint_eval_errors,
    }


def evaluate_checkpoint_snapshot(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    source: str,
    checkpoint_index: int,
    turn: int,
    assistant_message_id: str | None,
    hidden_evaluator_module: str,
    wall_seconds: float,
    permission_denials_delta: int = 0,
    verify_runner: Callable[[Path, Path], int] | None = None,
    hidden_runner: Callable[[Path, Path], int] | None = None,
) -> dict[str, Any]:
    checkpoint_root = run_dir / "solution_latency_checkpoints" / f"checkpoint_{checkpoint_index:04d}"
    checkpoint_root.mkdir(parents=True, exist_ok=True)

    temp_root, snapshot_root = _snapshot_repo(repo_root)
    verify_runner = verify_runner or _default_verify_runner
    hidden_runner = hidden_runner or _default_hidden_runner(hidden_evaluator_module)
    checkpoint_eval_errors: list[str] = []

    try:
        verify_exit = verify_runner(snapshot_root, checkpoint_root / "verification.txt")
    except Exception as exc:  # pragma: no cover - defensive guard
        verify_exit = 1
        checkpoint_eval_errors.append(f"verify: {exc.__class__.__name__}: {exc}")
        _write_text(checkpoint_root / "verification.txt", f"{exc.__class__.__name__}: {exc}\n")

    try:
        hidden_exit = hidden_runner(snapshot_root, checkpoint_root / "hidden_evaluator.txt")
    except Exception as exc:  # pragma: no cover - defensive guard
        hidden_exit = 1
        checkpoint_eval_errors.append(f"hidden: {exc.__class__.__name__}: {exc}")
        _write_text(checkpoint_root / "hidden_evaluator.txt", f"{exc.__class__.__name__}: {exc}\n")

    functional_green = verify_exit == 0 and hidden_exit == 0
    bench_ready_green, bench_ready_issues = is_bench_ready_green(arm_slug, snapshot_root, functional_green)
    if bench_ready_issues:
        _write_text(checkpoint_root / "bench_ready_issues.txt", "\n".join(bench_ready_issues) + "\n")

    record = _checkpoint_record(
        run_id=run_id,
        task_slug=task_slug,
        arm_slug=arm_slug,
        phase=phase,
        source=source,
        checkpoint_index=checkpoint_index,
        turn=turn,
        assistant_message_id=assistant_message_id,
        wall_seconds=wall_seconds,
        verify_exit=verify_exit,
        hidden_exit=hidden_exit,
        functional_green=functional_green,
        bench_ready_green=bench_ready_green,
        permission_denials_delta=permission_denials_delta,
        checkpoint_eval_errors=checkpoint_eval_errors,
    )

    _append_jsonl(run_dir / "turn_events.jsonl", record)
    _write_json(checkpoint_root / "checkpoint.json", record)
    shutil.rmtree(temp_root, ignore_errors=True)
    return record


def _event_message_id(event: dict[str, Any]) -> str | None:
    message = event.get("message")
    if not isinstance(message, dict):
        return None
    message_id = message.get("id")
    return message_id if isinstance(message_id, str) and message_id.strip() else None


def _event_content(event: dict[str, Any]) -> list[dict[str, Any]]:
    message = event.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [item for item in content if isinstance(item, dict)]


def _tool_name_from_content_block(block: dict[str, Any]) -> str | None:
    name = block.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    tool = block.get("tool")
    if isinstance(tool, str) and tool.strip():
        return tool.strip()
    return None


def _tool_use_id_from_block(block: dict[str, Any]) -> str | None:
    for key in ("id", "tool_use_id"):
        value = block.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _is_file_changing_tool(tool_name: str | None) -> bool:
    if not tool_name:
        return False
    return tool_name in FILE_CHANGING_TOOLS


def _event_permission_denials_total(event: dict[str, Any]) -> int | None:
    denials = event.get("permission_denials")
    if isinstance(denials, list):
        return len(denials)
    return None


def _event_tool_result_ids(event: dict[str, Any]) -> list[str]:
    message = event.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    ids: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_result":
            continue
        tool_use_id = block.get("tool_use_id")
        if isinstance(tool_use_id, str) and tool_use_id.strip():
            ids.append(tool_use_id.strip())
    return ids


def _event_to_line(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True)


def _checkpoint_current_turn(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    source: str,
    checkpoint_index: int,
    turn: int,
    assistant_message_id: str | None,
    hidden_evaluator_module: str,
    start_time: float,
    permission_denials_delta: int,
) -> dict[str, Any]:
    wall_seconds = round(time.monotonic() - start_time, 3)
    try:
        return evaluate_checkpoint_snapshot(
            repo_root=repo_root,
            run_dir=run_dir,
            run_id=run_id,
            task_slug=task_slug,
            arm_slug=arm_slug,
            phase=phase,
            source=source,
            checkpoint_index=checkpoint_index,
            turn=turn,
            assistant_message_id=assistant_message_id,
            hidden_evaluator_module=hidden_evaluator_module,
            wall_seconds=wall_seconds,
            permission_denials_delta=permission_denials_delta,
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        checkpoint_root = run_dir / "solution_latency_checkpoints" / f"checkpoint_{checkpoint_index:04d}"
        checkpoint_root.mkdir(parents=True, exist_ok=True)
        error = f"{exc.__class__.__name__}: {exc}"
        _write_text(checkpoint_root / "checkpoint_error.txt", error + "\n")
        record = _checkpoint_record(
            run_id=run_id,
            task_slug=task_slug,
            arm_slug=arm_slug,
            phase=phase,
            source=source,
            checkpoint_index=checkpoint_index,
            turn=turn,
            assistant_message_id=assistant_message_id,
            wall_seconds=wall_seconds,
            verify_exit=1,
            hidden_exit=1,
            functional_green=False,
            bench_ready_green=False,
            permission_denials_delta=permission_denials_delta,
            checkpoint_eval_errors=[error],
        )
        _append_jsonl(run_dir / "turn_events.jsonl", record)
        _write_json(checkpoint_root / "checkpoint.json", record)
        return record


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
) -> int:
    stdout_path = run_dir / "claude_stdout.txt"
    stderr_path = run_dir / "claude_stderr.txt"
    events_path = run_dir / "claude_events.jsonl"
    exit_path = run_dir / "claude_exit_code.txt"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    _write_text(stdout_path, "")
    _write_text(stderr_path, "")
    _write_text(events_path, "")

    command = [
        claude_cmd,
        "-p",
    ]
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
            STREAM_JSON_MODE.replace("_", "-"),
            "--verbose",
            "--include-partial-messages",
            prompt_text,
        ]
    )

    proc = subprocess.Popen(
        command,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    stdout_queue: queue.Queue[str | object] = queue.Queue()

    def _pump_stdout() -> None:
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                stdout_queue.put(line)
        finally:
            stdout_queue.put(_STOP)

    def _pump_stderr() -> None:
        assert proc.stderr is not None
        with stderr_path.open("w", encoding="utf-8") as handle:
            for line in proc.stderr:
                handle.write(line)
                handle.flush()

    stdout_thread = threading.Thread(target=_pump_stdout, name="claude-stdout-pump", daemon=True)
    stderr_thread = threading.Thread(target=_pump_stderr, name="claude-stderr-pump", daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    current_message_id: str | None = None
    current_turn = 0
    current_turn_had_file_change = False
    current_turn_checkpointed = False
    current_turn_completed = False
    turn_checkpoint_counts: dict[str, int] = {}
    tool_use_to_name: dict[str, str] = {}
    tool_use_to_file_change: dict[str, bool] = {}
    checkpoint_index = 0
    permission_denials_total = 0
    last_checkpoint_permission_denials_total = 0
    start_time = time.monotonic()
    trace_recorder = AgentTurnTraceRecorder(
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

    def checkpoint_current_turn(trigger: str) -> None:
        nonlocal checkpoint_index, current_turn_checkpointed, current_turn_completed, last_checkpoint_permission_denials_total
        if current_message_id is None or not current_turn_had_file_change:
            return
        if current_turn_checkpointed:
            return
        checkpoint_index += 1
        record = _checkpoint_current_turn(
            repo_root=repo_root,
            run_dir=run_dir,
            run_id=run_id,
            task_slug=task_slug,
            arm_slug=arm_slug,
            phase=phase,
            source=STREAM_JSON_MODE,
            checkpoint_index=checkpoint_index,
            turn=current_turn,
            assistant_message_id=current_message_id,
            hidden_evaluator_module=hidden_evaluator_module,
            start_time=start_time,
            permission_denials_delta=max(permission_denials_total - last_checkpoint_permission_denials_total, 0),
        )
        last_checkpoint_permission_denials_total = permission_denials_total
        turn_checkpoint_counts[str(current_turn)] = turn_checkpoint_counts.get(str(current_turn), 0) + 1
        current_turn_checkpointed = True
        if not current_turn_completed:
            trace_recorder.record_turn_completed(
                turn_index=current_turn,
                provider_event_type="checkpoint",
                message_id=current_message_id,
                wall_seconds=record["wall_seconds"],
                notes=[trigger],
            )
            current_turn_completed = True
        trace_recorder.record_checkpoint(
            checkpoint_index=checkpoint_index,
            turn_index=current_turn,
            provider_event_type="checkpoint",
            assistant_message_id=current_message_id,
            wall_seconds=record["wall_seconds"],
            verify_exit=record["verify_exit"],
            hidden_evaluator_exit=record["hidden_evaluator_exit"],
            functional_green=record["functional_green"],
            bench_ready_green=record["bench_ready_green"],
            permission_denials_delta=record["permission_denials_delta"],
            checkpoint_eval_errors=record["checkpoint_eval_errors"],
            notes=[trigger],
        )
        _write_text(
            run_dir / "solution_latency_checkpoints" / f"checkpoint_{checkpoint_index:04d}" / "trigger.txt",
            f"{trigger}\n",
        )

    def handle_event(event: dict[str, Any]) -> None:
        nonlocal current_message_id, current_turn, current_turn_had_file_change, current_turn_checkpointed, current_turn_completed, permission_denials_total

        event_type = str(event.get("type") or "").lower()
        total = _event_permission_denials_total(event)
        if total is not None:
            permission_denials_total = total

        if event_type == "assistant":
            message_id = _event_message_id(event)
            if message_id and message_id != current_message_id:
                checkpoint_current_turn(trigger="assistant_boundary")
                current_message_id = message_id
                current_turn += 1
                current_turn_had_file_change = False
                current_turn_checkpointed = False
                current_turn_completed = False
                trace_recorder.record_turn_started(
                    turn_index=current_turn,
                    provider_event_type="assistant",
                    message_id=current_message_id,
                    wall_seconds=round(time.monotonic() - start_time, 3),
                )
                trace_recorder.record_assistant_message(
                    turn_index=current_turn,
                    provider_event_type="assistant",
                    message_id=current_message_id,
                    wall_seconds=round(time.monotonic() - start_time, 3),
                )
                for block in _event_content(event):
                    if block.get("type") != "tool_use":
                        continue
                    tool_use_id = _tool_use_id_from_block(block)
                    tool_name = _tool_name_from_content_block(block)
                    if tool_use_id and tool_name:
                        tool_use_to_name[tool_use_id] = tool_name
                        tool_use_to_file_change[tool_use_id] = _is_file_changing_tool(tool_name)
                        trace_recorder.record_tool_use(
                            turn_index=current_turn,
                            provider_event_type="assistant",
                            tool_use_id=tool_use_id,
                            tool_name=tool_name,
                            message_id=current_message_id,
                            wall_seconds=round(time.monotonic() - start_time, 3),
                            file_changing_tool=tool_use_to_file_change[tool_use_id],
                        )
                return

            for block in _event_content(event):
                if block.get("type") != "tool_use":
                    continue
                tool_use_id = _tool_use_id_from_block(block)
                tool_name = _tool_name_from_content_block(block)
                if tool_use_id and tool_name:
                    tool_use_to_name[tool_use_id] = tool_name
                    tool_use_to_file_change[tool_use_id] = _is_file_changing_tool(tool_name)
                    trace_recorder.record_tool_use(
                        turn_index=current_turn or None,
                        provider_event_type="assistant",
                        tool_use_id=tool_use_id,
                        tool_name=tool_name,
                        message_id=current_message_id,
                        wall_seconds=round(time.monotonic() - start_time, 3),
                        file_changing_tool=tool_use_to_file_change[tool_use_id],
                    )

        elif event_type == "user":
            file_change_detected = False
            for tool_use_id in _event_tool_result_ids(event):
                if tool_use_to_file_change.get(tool_use_id):
                    file_change_detected = True
                trace_recorder.record_tool_result(
                    turn_index=current_turn or None,
                    provider_event_type="user",
                    tool_use_id=tool_use_id,
                    tool_name=tool_use_to_name.get(tool_use_id),
                    message_id=current_message_id,
                    wall_seconds=round(time.monotonic() - start_time, 3),
                    file_changing_tool=tool_use_to_file_change.get(tool_use_id),
                )
            if file_change_detected:
                current_turn_had_file_change = True
        elif event_type == "result":
            checkpoint_current_turn(trigger="final_result")
            if current_message_id is not None and not current_turn_completed:
                trace_recorder.record_turn_completed(
                    turn_index=current_turn or None,
                    provider_event_type="result",
                    message_id=current_message_id,
                    wall_seconds=round(time.monotonic() - start_time, 3),
                    notes=["final result observed"],
                )
                current_turn_completed = True

    while True:
        item = stdout_queue.get()
        if item is _STOP:
            break
        stdout_line = str(item)
        with stdout_path.open("a", encoding="utf-8") as stdout_handle:
            stdout_handle.write(stdout_line)
        with events_path.open("a", encoding="utf-8") as events_handle:
            events_handle.write(stdout_line)
        try:
            parsed = json.loads(stdout_line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            handle_event(parsed)

    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    proc.wait()

    if current_message_id is not None and current_turn_had_file_change:
        checkpoint_current_turn(trigger="stream_end")

    exit_code = proc.returncode or 0
    trace_recorder.record_run_result(
        provider_event_type="result",
        wall_seconds=round(time.monotonic() - start_time, 3),
        exit_code=exit_code,
    )
    trace_recorder.finalize()
    _write_text(exit_path, f"{exit_code}\n")
    return exit_code


def _tracked_file_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _is_relevant_tracked_path(path: Path) -> bool:
    if path.name in {"VERIFY.sh", "TASK.md", "SKILL_RUNTIME_PROOF.md"}:
        return True
    if any(part in {"src", "tests", "docs", "fixtures", "tasks", "benchmark_harness", "arms"} for part in path.parts):
        return True
    return path.suffix.lower() in {".py", ".md", ".txt", ".sh", ".json", ".csv", ".yml", ".yaml", ".toml", ".ini"}


def _git_tracked_files(repo_root: Path) -> list[Path]:
    try:
        proc = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    if proc.returncode != 0:
        return []
    files = []
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        path = repo_root / stripped
        if _is_relevant_tracked_path(Path(stripped)) and path.exists():
            files.append(path)
    return files


def _poll_signature(repo_root: Path, tracked_files: list[Path]) -> dict[str, tuple[int, int] | None]:
    return {str(path.relative_to(repo_root)): _tracked_file_signature(path) for path in tracked_files}


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
) -> int:
    stdout_path = run_dir / "claude_stdout.txt"
    stderr_path = run_dir / "claude_stderr.txt"
    exit_path = run_dir / "claude_exit_code.txt"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    _write_text(stdout_path, "")
    _write_text(stderr_path, "")

    command = [
        claude_cmd,
        "-p",
    ]
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
            "json",
            prompt_text,
        ]
    )

    proc = subprocess.Popen(
        command,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
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

    checkpoint_index = 0
    start_time = time.monotonic()
    tracked_files = _git_tracked_files(repo_root)
    last_signature = _poll_signature(repo_root, tracked_files)
    permission_denials_total = 0
    last_checkpoint_permission_denials_total = 0
    trace_recorder = AgentTurnTraceRecorder(
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

    while proc.poll() is None:
        time.sleep(1.0)
        current_signature = _poll_signature(repo_root, tracked_files)
        if current_signature == last_signature:
            continue
        checkpoint_index += 1
        wall_seconds = round(time.monotonic() - start_time, 3)
        trace_recorder.record_file_change_observed(
            turn_index=checkpoint_index,
            provider_event_type="mtime_polling",
            checkpoint_index=checkpoint_index,
            wall_seconds=wall_seconds,
            notes=["mtime polling detected a tracked file change"],
        )
        record = _checkpoint_current_turn(
            repo_root=repo_root,
            run_dir=run_dir,
            run_id=run_id,
            task_slug=task_slug,
            arm_slug=arm_slug,
            phase=phase,
            source=MTIME_POLLING_MODE,
            checkpoint_index=checkpoint_index,
            turn=checkpoint_index,
            assistant_message_id=None,
            hidden_evaluator_module=hidden_evaluator_module,
            start_time=start_time,
            permission_denials_delta=max(permission_denials_total - last_checkpoint_permission_denials_total, 0),
        )
        trace_recorder.record_checkpoint(
            checkpoint_index=checkpoint_index,
            turn_index=checkpoint_index,
            provider_event_type="mtime_polling",
            assistant_message_id=None,
            wall_seconds=record["wall_seconds"],
            verify_exit=record["verify_exit"],
            hidden_evaluator_exit=record["hidden_evaluator_exit"],
            functional_green=record["functional_green"],
            bench_ready_green=record["bench_ready_green"],
            permission_denials_delta=record["permission_denials_delta"],
            checkpoint_eval_errors=record["checkpoint_eval_errors"],
            notes=["mtime polling checkpoint"],
        )
        trace_recorder.record_turn_completed(
            turn_index=checkpoint_index,
            provider_event_type="mtime_polling",
            wall_seconds=record["wall_seconds"],
            notes=["mtime polling checkpoint"],
        )
        last_checkpoint_permission_denials_total = permission_denials_total
        last_signature = current_signature

    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    proc.wait()
    exit_code = proc.returncode or 0
    trace_recorder.record_run_result(
        provider_event_type="result",
        wall_seconds=round(time.monotonic() - start_time, 3),
        exit_code=exit_code,
    )
    trace_recorder.finalize()
    _write_text(exit_path, f"{exit_code}\n")
    return exit_code


def _stream_to_file(stream: Any, output_path: Path) -> None:
    if stream is None:
        return
    with output_path.open("a", encoding="utf-8") as handle:
        for line in stream:
            handle.write(line)
            handle.flush()


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
) -> int:
    prompt_text = prompt_file.read_text(encoding="utf-8")
    run_dir.mkdir(parents=True, exist_ok=True)

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
            )
        raise ValueError(f"unknown observation mode: {mode}")
    except Exception as exc:  # pragma: no cover - best-effort error handling
        _write_text(run_dir / "solution_latency_observer_error.txt", f"{exc.__class__.__name__}: {exc}\n")
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Claude with solution-latency observation.")
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
    args = parser.parse_args(argv)

    if args.command == "run":
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
        )
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
