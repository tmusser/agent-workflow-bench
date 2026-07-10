from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from benchmark_harness.skill_routing_summary import summarize_repo as summarize_skill_routing_repo
from benchmark_harness.skill_trace_summary import summarize_repo as summarize_skill_trace_repo

SCHEMA_VERSION = 1
TRACE_FILENAME = "agent_turn_trace.jsonl"
TRACE_SUMMARY_FILENAME = "agent_turn_trace_summary.json"

PROVIDER_CLAUDE = "claude"
PROVIDER_CODEX = "codex"

TRACE_SOURCE_CLAUDE_STREAM_JSON = "claude_stream_json"
TRACE_SOURCE_CLAUDE_MTIME_POLLING = "claude_mtime_polling"
TRACE_SOURCE_CODEX_JSONL = "codex_jsonl"
TRACE_SOURCE_CODEX_JSON = "codex_json"
TRACE_SOURCE_UNKNOWN = "unknown"

TRACE_FIDELITY_TURN_EVENT = "turn_event"
TRACE_FIDELITY_CHECKPOINT_ONLY = "checkpoint_only"
TRACE_FIDELITY_RUN_LEVEL_ONLY = "run_level_only"

OBSERVED_NOTE = "Safe metadata only; raw provider content omitted."
CLAUSE_OBSERVED_NOTE = "Safe metadata only; raw Claude content omitted."

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

CODEX_AUDIT_ARTIFACTS = {
    "BUGS.md",
    "HANDOFF.md",
    "PLAN.md",
    "SKILL_RUNTIME_PROOF.md",
    "SKILL_TRACE.jsonl",
    "SPEC.md",
    "VERIFY.md",
}
CODEX_PROOF_ARTIFACTS = {"SKILL_RUNTIME_PROOF.md", "SKILL_TRACE.jsonl"}
CODEX_SOURCE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".swift",
    ".ts",
    ".tsx",
}

FINAL_ONLY_NOTE = "final_only_no_per_turn_trace"
OBSERVED_TRACE_NOTE = "observed_from_per_turn_trace"
OBSERVED_MTIME_NOTE = "observed_from_mtime_polling"
NOT_OBSERVABLE_NOTE = "not_observable"


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


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return None


def _safe_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _normalize_turn_index(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _is_file_changing_tool(tool_name: str | None) -> bool:
    return bool(tool_name and tool_name in FILE_CHANGING_TOOLS)


def _value_from_keys(payload: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in payload:
            value = payload.get(key)
            if value is not None:
                return value
    return None


def _extract_message_id(payload: dict[str, Any]) -> str | None:
    message = payload.get("message")
    if isinstance(message, dict):
        message_id = _safe_str(message.get("id"))
        if message_id:
            return message_id
    for key in ("message_id", "messageId", "id", "uuid"):
        value = _safe_str(payload.get(key))
        if value:
            return value
    return None


def _extract_tool_use_id(payload: dict[str, Any]) -> str | None:
    for key in ("tool_use_id", "toolUseId", "tool_call_id", "toolCallId", "call_id", "callId", "id"):
        value = _safe_str(payload.get(key))
        if value:
            return value
    return None


def _extract_tool_name(payload: dict[str, Any]) -> str | None:
    for key in ("tool_name", "toolName", "name", "tool", "tool_type", "toolType"):
        value = _safe_str(payload.get(key))
        if value:
            return value
    return None


def _extract_content_blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    message = payload.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, list):
            return [item for item in content if isinstance(item, dict)]
    content = payload.get("content")
    if isinstance(content, list):
        return [item for item in content if isinstance(item, dict)]
    return []


def _extract_item_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    item = payload.get("item")
    if isinstance(item, dict):
        return item
    content = payload.get("content")
    if isinstance(content, dict):
        return content
    return None


def _codex_item_type(item: dict[str, Any]) -> str:
    item_type = _safe_str(item.get("type")) or _safe_str(item.get("item_type")) or _safe_str(item.get("kind"))
    return item_type.lower().replace(".", "_").replace("-", "_") if item_type else ""


def _codex_item_status(item: dict[str, Any]) -> str | None:
    value = _safe_str(item.get("status")) or _safe_str(item.get("state"))
    return value.lower().replace(".", "_").replace("-", "_") if value else None


def _codex_command_category(item: dict[str, Any]) -> str | None:
    command = _safe_str(item.get("command"))
    if command is None:
        return None
    lowered = command.lower()
    if "validate_skill_runtime_proof" in lowered or "skill_runtime_proof.md" in lowered and "python" in lowered:
        return "proof_validation"
    if any(marker in lowered for marker in ("verify.sh", "hidden_evaluator", "benchmark_harness.evaluators")):
        return "verification"
    if any(
        marker in lowered
        for marker in (
            "pytest",
            "unittest",
            "npm test",
            "pnpm test",
            "yarn test",
            "cargo test",
            "go test",
            "ruff",
            "mypy",
            "markdownlint",
        )
    ):
        return "test"
    if any(marker in lowered for marker in ("git status", "git diff", "git log", "git show")):
        return "git"
    stripped = lowered.lstrip()
    if stripped.startswith(("sed ", "cat ", "head ", "tail ", "rg ", "grep ", "find ", "ls ", "pwd")):
        return "inspection"
    if any(marker in lowered for marker in (" | sed ", " | cat ", " | head ", " | tail ", " | rg ", " | grep ")):
        return "inspection"
    return "other"


def _codex_file_change_metadata(item: dict[str, Any]) -> tuple[list[str], list[str], int]:
    changes = item.get("changes")
    if not isinstance(changes, list):
        return [], [], 0

    categories: set[str] = set()
    audit_artifacts: set[str] = set()
    path_count = 0
    for change in changes:
        if not isinstance(change, dict):
            continue
        raw_path = _safe_str(change.get("path"))
        if raw_path is None:
            continue
        path_count += 1
        normalized = raw_path.replace("\\", "/")
        name = normalized.rsplit("/", 1)[-1]
        lowered = normalized.lower()
        if name in CODEX_AUDIT_ARTIFACTS:
            categories.add("audit_artifact")
            audit_artifacts.add(name)
        elif "/tests/" in lowered or name.lower().startswith("test_") or name.lower().endswith("_test.py"):
            categories.add("test")
        elif Path(name).suffix.lower() in CODEX_SOURCE_SUFFIXES:
            categories.add("source")
        else:
            categories.add("other")
    return sorted(categories), sorted(audit_artifacts), path_count


def _resolve_codex_turn_index(
    current_turn_index: int | None,
    explicit_turn_index: int | None,
    *,
    start_new_turn: bool = False,
    create_if_missing: bool = False,
) -> int | None:
    if explicit_turn_index is not None:
        return explicit_turn_index
    if start_new_turn:
        return (current_turn_index or 0) + 1
    if current_turn_index is not None:
        return current_turn_index
    if create_if_missing:
        return 1
    return None


def _extract_tool_calls(payload: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for key in ("tool_calls", "toolCalls", "tool_uses", "toolUses", "actions"):
        value = payload.get(key)
        if isinstance(value, list):
            calls.extend([item for item in value if isinstance(item, dict)])
    return calls


def _extract_turn_index(payload: dict[str, Any]) -> int | None:
    for key in (
        "turn_index",
        "turnIndex",
        "turn",
        "turn_number",
        "turnNumber",
        "index",
    ):
        turn_index = _normalize_turn_index(payload.get(key))
        if turn_index is not None:
            return turn_index
    return None


def _extract_wall_seconds(payload: dict[str, Any]) -> float | None:
    for key in ("wall_seconds", "wallClockSeconds", "wall_clock_seconds", "elapsed_seconds", "duration_seconds"):
        value = _coerce_float(payload.get(key))
        if value is not None:
            return round(value, 3)
    return None


def _extract_permission_denials_delta(payload: dict[str, Any]) -> int | None:
    for key in ("permission_denials_delta", "permissionDenialsDelta", "permission_denials_count_delta"):
        value = _coerce_int(payload.get(key))
        if value is not None:
            return max(value, 0)
    return None


def _extract_exit_code(payload: dict[str, Any]) -> int | None:
    for key in ("verify_exit", "verification_exit", "hidden_exit", "hidden_evaluator_exit", "exit_code", "exitCode"):
        value = _coerce_int(payload.get(key))
        if value is not None:
            return value
    return None


def _ordered_turn_key(turn_key: str) -> tuple[int, str]:
    try:
        return int(turn_key), turn_key
    except ValueError:
        return 10**9, turn_key


def _flatten_event_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for row in rows:
        flattened.append(row)
    return flattened


def _safe_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_safe_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _trace_source_for_solution_latency(trace_source: str, trace_fidelity: str) -> str:
    if trace_fidelity == TRACE_FIDELITY_RUN_LEVEL_ONLY:
        return FINAL_ONLY_NOTE
    if trace_fidelity == TRACE_FIDELITY_CHECKPOINT_ONLY:
        if trace_source == TRACE_SOURCE_CLAUDE_MTIME_POLLING:
            return "mtime_polling"
        return trace_source
    if trace_source == TRACE_SOURCE_CLAUDE_STREAM_JSON:
        return "stream_json"
    return trace_source


def _solution_latency_note(trace_source: str, trace_fidelity: str, observable: bool) -> str:
    if trace_fidelity == TRACE_FIDELITY_CHECKPOINT_ONLY:
        return OBSERVED_MTIME_NOTE
    if observable:
        return OBSERVED_TRACE_NOTE
    if trace_fidelity == TRACE_FIDELITY_RUN_LEVEL_ONLY:
        return NOT_OBSERVABLE_NOTE
    if trace_source == TRACE_SOURCE_CLAUDE_MTIME_POLLING:
        return OBSERVED_MTIME_NOTE
    return NOT_OBSERVABLE_NOTE


def _turns_from_rows(rows: list[dict[str, Any]]) -> list[int]:
    turns = sorted({
        turn_index
        for row in rows
        if (turn_index := _coerce_int(row.get("turn_index"))) is not None
    })
    return turns


def _flatten_checkpoint_errors(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for row in rows:
        if row.get("event_kind") != "checkpoint":
            continue
        value = row.get("checkpoint_eval_errors")
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    errors.append(item.strip())
                elif item is not None:
                    errors.append(str(item))
        elif isinstance(value, str) and value.strip():
            errors.append(value.strip())
    return errors


def _summarize_skill_evidence(
    repo_root: Path | None,
    *,
    run_id: str,
    phase: str,
    arm_slug: str,
) -> dict[str, Any]:
    if repo_root is None:
        return {
            "skill_trace_present": False,
            "skill_trace_evidence_level": "none",
            "skill_trace_claim_boundary": None,
            "declared_available_skills": [],
            "declared_considered_skills": [],
            "declared_invoked_skills": [],
            "declared_skipped_skills": [],
            "declared_events_by_turn": {},
            "artifact_inferred_skills": [],
            "skill_runtime_context_present": False,
        }

    trace_summary = summarize_skill_trace_repo(repo_root, run_id=run_id, phase=phase)
    routing_summary = summarize_skill_routing_repo(repo_root, run_id=run_id, phase=phase, arm_slug=arm_slug)
    context_present = (repo_root / ".benchmark" / "SKILL_RUNTIME_CONTEXT.md").is_file()
    artifact_inferred_skills = routing_summary.summary.get("skills", [])
    if not isinstance(artifact_inferred_skills, list):
        artifact_inferred_skills = []

    if trace_summary.trace_present:
        evidence_level = trace_summary.evidence_level
    elif artifact_inferred_skills:
        evidence_level = "artifact_inferred"
    elif context_present:
        evidence_level = "availability_only"
    else:
        evidence_level = "none"

    return {
        "skill_trace_present": trace_summary.trace_present,
        "skill_trace_evidence_level": evidence_level,
        "skill_trace_claim_boundary": trace_summary.claim_boundary,
        "declared_available_skills": trace_summary.declared_available_skills,
        "declared_considered_skills": trace_summary.declared_considered_skills,
        "declared_invoked_skills": trace_summary.declared_invoked_skills,
        "declared_skipped_skills": trace_summary.declared_skipped_skills,
        "declared_events_by_turn": trace_summary.declared_events_by_turn,
        "artifact_inferred_skills": artifact_inferred_skills,
        "skill_runtime_context_present": context_present,
    }


@dataclass
class AgentTurnTraceRecorder:
    run_id: str
    task_slug: str
    arm_slug: str
    phase: str
    provider: str
    runner: str
    trace_source: str
    trace_fidelity: str
    repo_root: Path | None = None
    jsonl_path: Path | None = None
    summary_path: Path | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    _tool_use_metadata: dict[str, dict[str, Any]] = field(default_factory=dict, init=False, repr=False)
    _file_change_observed_ids: set[str] = field(default_factory=set, init=False, repr=False)
    _provider_item_indices: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _provider_item_index: int = field(default=0, init=False, repr=False)
    _event_index: int = field(default=0, init=False, repr=False)

    def _promote_trace_fidelity(self, fidelity: str) -> None:
        if fidelity == TRACE_FIDELITY_TURN_EVENT:
            self.trace_fidelity = TRACE_FIDELITY_TURN_EVENT

    def _base_row(self, event_kind: str, **fields: Any) -> dict[str, Any]:
        row: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "task_slug": self.task_slug,
            "arm_slug": self.arm_slug,
            "phase": self.phase,
            "provider": self.provider,
            "runner": self.runner,
            "trace_source": self.trace_source,
            "trace_fidelity": self.trace_fidelity,
            "event_kind": event_kind,
        }
        for key, value in fields.items():
            if value is None:
                continue
            if key == "notes":
                notes = [note for note in value if isinstance(note, str) and note.strip()]
                if notes:
                    row[key] = notes
                continue
            row[key] = _safe_jsonable(value)
        return row

    def _emit_row(self, event_kind: str, **fields: Any) -> dict[str, Any]:
        self._event_index += 1
        row = self._base_row(event_kind, event_index=self._event_index, **fields)
        self.rows.append(row)
        if self.jsonl_path is not None:
            _append_jsonl(self.jsonl_path, row)
        return row

    def has_tool_use_id(self, tool_use_id: str | None) -> bool:
        return bool(tool_use_id and tool_use_id in self._tool_use_metadata)

    def record_provider_item(
        self,
        *,
        provider_event_type: str,
        provider_item_type: str,
        provider_item_lifecycle: str,
        provider_item_status: str | None,
        item_id: str | None,
        turn_index: int | None,
        wall_seconds: float | None,
        command_category: str | None = None,
        file_change_categories: list[str] | None = None,
        audit_artifacts_changed: list[str] | None = None,
        paths_changed_count: int = 0,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        item_key = item_id or f"anonymous:{provider_event_type}:{self._event_index + 1}"
        if item_key not in self._provider_item_indices:
            self._provider_item_index += 1
            self._provider_item_indices[item_key] = self._provider_item_index
        return self._emit_row(
            "provider_item",
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            provider_item_index=self._provider_item_indices[item_key],
            provider_item_type=provider_item_type,
            provider_item_lifecycle=provider_item_lifecycle,
            provider_item_status=provider_item_status,
            tool_use_id=item_id,
            command_category=command_category,
            file_change_categories=file_change_categories or [],
            audit_artifacts_changed=audit_artifacts_changed or [],
            paths_changed_count=max(paths_changed_count, 0),
            wall_seconds=wall_seconds,
            notes=notes or [OBSERVED_NOTE],
        )

    def record_turn_started(
        self,
        *,
        turn_index: int | None,
        provider_event_type: str,
        message_id: str | None = None,
        wall_seconds: float | None = None,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        if turn_index is not None:
            self._promote_trace_fidelity(TRACE_FIDELITY_TURN_EVENT)
        return self._emit_row(
            "turn_started",
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            message_id=message_id,
            wall_seconds=wall_seconds,
            notes=notes or [OBSERVED_NOTE],
        )

    def record_assistant_message(
        self,
        *,
        turn_index: int | None,
        provider_event_type: str,
        message_id: str | None = None,
        wall_seconds: float | None = None,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        if turn_index is not None:
            self._promote_trace_fidelity(TRACE_FIDELITY_TURN_EVENT)
        return self._emit_row(
            "assistant_message",
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            message_id=message_id,
            wall_seconds=wall_seconds,
            notes=notes or [OBSERVED_NOTE],
        )

    def record_tool_use(
        self,
        *,
        turn_index: int | None,
        provider_event_type: str,
        tool_use_id: str | None,
        tool_name: str | None,
        message_id: str | None = None,
        wall_seconds: float | None = None,
        file_changing_tool: bool | None = None,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        if turn_index is not None:
            self._promote_trace_fidelity(TRACE_FIDELITY_TURN_EVENT)
        file_changing = _is_file_changing_tool(tool_name) if file_changing_tool is None else bool(file_changing_tool)
        if tool_use_id:
            self._tool_use_metadata[tool_use_id] = {
                "tool_name": tool_name,
                "file_changing_tool": file_changing,
                "turn_index": turn_index,
                "message_id": message_id,
            }
        row = self._emit_row(
            "tool_use",
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            message_id=message_id,
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            file_changing_tool=file_changing,
            wall_seconds=wall_seconds,
            notes=notes or [OBSERVED_NOTE],
        )
        if file_changing and tool_use_id and tool_use_id not in self._file_change_observed_ids:
            self.record_file_change_observed(
                turn_index=turn_index,
                provider_event_type=provider_event_type,
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                message_id=message_id,
                wall_seconds=wall_seconds,
                notes=["file-changing tool observed"],
            )
        return row

    def record_tool_result(
        self,
        *,
        turn_index: int | None,
        provider_event_type: str,
        tool_use_id: str | None,
        tool_name: str | None = None,
        message_id: str | None = None,
        wall_seconds: float | None = None,
        file_changing_tool: bool | None = None,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        if turn_index is not None:
            self._promote_trace_fidelity(TRACE_FIDELITY_TURN_EVENT)
        metadata = self._tool_use_metadata.get(tool_use_id or "", {})
        if tool_name is None:
            tool_name = _safe_str(metadata.get("tool_name"))
        if file_changing_tool is None:
            file_changing_tool = bool(metadata.get("file_changing_tool", _is_file_changing_tool(tool_name)))
        row = self._emit_row(
            "tool_result",
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            message_id=message_id,
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            file_changing_tool=file_changing_tool,
            wall_seconds=wall_seconds,
            notes=notes or [OBSERVED_NOTE],
        )
        return row

    def record_file_change_observed(
        self,
        *,
        turn_index: int | None,
        provider_event_type: str,
        tool_use_id: str | None = None,
        tool_name: str | None = None,
        checkpoint_index: int | None = None,
        message_id: str | None = None,
        wall_seconds: float | None = None,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        if tool_use_id:
            self._file_change_observed_ids.add(tool_use_id)
        return self._emit_row(
            "file_change_observed",
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            message_id=message_id,
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            checkpoint_index=checkpoint_index,
            file_changing_tool=True,
            wall_seconds=wall_seconds,
            notes=notes or [OBSERVED_NOTE],
        )

    def record_checkpoint(
        self,
        *,
        checkpoint_index: int,
        turn_index: int | None,
        provider_event_type: str,
        assistant_message_id: str | None,
        wall_seconds: float | None,
        verify_exit: int | None,
        hidden_evaluator_exit: int | None,
        functional_green: bool | None,
        bench_ready_green: bool | None,
        permission_denials_delta: int | None = None,
        checkpoint_eval_errors: list[str] | None = None,
        provider_item_index: int | None = None,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._emit_row(
            "checkpoint",
            checkpoint_index=checkpoint_index,
            turn_index=turn_index,
            provider_item_index=provider_item_index,
            provider_event_type=provider_event_type,
            message_id=assistant_message_id,
            wall_seconds=wall_seconds,
            verify_exit=verify_exit,
            hidden_evaluator_exit=hidden_evaluator_exit,
            functional_green=functional_green,
            bench_ready_green=bench_ready_green,
            permission_denials_delta=max(permission_denials_delta or 0, 0),
            checkpoint_eval_errors=checkpoint_eval_errors or [],
            notes=notes or [OBSERVED_NOTE],
        )

    def record_turn_completed(
        self,
        *,
        turn_index: int | None,
        provider_event_type: str,
        message_id: str | None = None,
        wall_seconds: float | None = None,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        if turn_index is not None:
            self._promote_trace_fidelity(TRACE_FIDELITY_TURN_EVENT)
        return self._emit_row(
            "turn_completed",
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            message_id=message_id,
            wall_seconds=wall_seconds,
            notes=notes or [OBSERVED_NOTE],
        )

    def record_run_result(
        self,
        *,
        provider_event_type: str,
        wall_seconds: float | None = None,
        turn_index: int | None = None,
        exit_code: int | None = None,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._emit_row(
            "run_result",
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            wall_seconds=wall_seconds,
            exit_code=exit_code,
            notes=notes or [OBSERVED_NOTE],
        )

    def record_provider_error(
        self,
        *,
        provider_event_type: str,
        wall_seconds: float | None = None,
        turn_index: int | None = None,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._emit_row(
            "provider_error",
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            wall_seconds=wall_seconds,
            notes=notes or [OBSERVED_NOTE],
        )

    def build_summary(self) -> dict[str, Any]:
        summary = _summarize_rows(
            self.rows,
            run_id=self.run_id,
            phase=self.phase,
            provider=self.provider,
            runner=self.runner,
            trace_source=self.trace_source,
            trace_fidelity=self.trace_fidelity,
            repo_root=self.repo_root,
            arm_slug=self.arm_slug,
        )
        if self.summary_path is not None:
            _write_json(self.summary_path, summary)
        return summary

    def finalize(self) -> dict[str, Any]:
        return self.build_summary()


def _summarize_provider_items(rows: list[dict[str, Any]]) -> dict[str, Any]:
    item_rows = [row for row in rows if row.get("event_kind") == "provider_item"]
    if not item_rows:
        return {
            "provider_item_timeline_observable": False,
            "provider_items_observed": 0,
            "command_execution_items_observed": 0,
            "file_change_items_observed": 0,
            "command_category_counts": {},
            "file_change_category_counts": {},
            "first_source_edit_item": None,
            "first_test_command_item": None,
            "first_verification_command_item": None,
            "first_audit_artifact_write_item": None,
            "first_skill_proof_write_item": None,
            "items_after_first_source_edit": None,
            "items_after_first_test_command": None,
            "items_after_first_audit_artifact_write": None,
            "provider_item_timeline_note": NOT_OBSERVABLE_NOTE,
        }

    unique_items: dict[int, dict[str, Any]] = {}
    for row in item_rows:
        item_index = _coerce_int(row.get("provider_item_index"))
        if item_index is not None:
            unique_items[item_index] = row
    ordered = [unique_items[index] for index in sorted(unique_items)]

    command_category_counts: dict[str, int] = {}
    file_change_category_counts: dict[str, int] = {}
    for row in ordered:
        category = _safe_str(row.get("command_category"))
        if category:
            command_category_counts[category] = command_category_counts.get(category, 0) + 1
        categories = row.get("file_change_categories")
        if isinstance(categories, list):
            for value in categories:
                category_value = _safe_str(value)
                if category_value:
                    file_change_category_counts[category_value] = file_change_category_counts.get(category_value, 0) + 1

    def first_item(predicate: Any) -> int | None:
        for row in ordered:
            if predicate(row):
                return _coerce_int(row.get("provider_item_index"))
        return None

    first_source_edit = first_item(lambda row: "source" in (row.get("file_change_categories") or []))
    first_test_command = first_item(lambda row: row.get("command_category") == "test")
    first_verification_command = first_item(
        lambda row: row.get("command_category") in {"verification", "proof_validation"}
    )
    first_audit_artifact = first_item(lambda row: "audit_artifact" in (row.get("file_change_categories") or []))
    first_skill_proof = first_item(
        lambda row: bool(CODEX_PROOF_ARTIFACTS.intersection(set(row.get("audit_artifacts_changed") or [])))
    )
    last_item = max(unique_items) if unique_items else None

    def items_after(index: int | None) -> int | None:
        if index is None or last_item is None:
            return None
        return max(last_item - index, 0)

    return {
        "provider_item_timeline_observable": True,
        "provider_items_observed": len(ordered),
        "command_execution_items_observed": sum(
            1 for row in ordered if row.get("provider_item_type") == "command_execution"
        ),
        "file_change_items_observed": sum(1 for row in ordered if row.get("provider_item_type") == "file_change"),
        "command_category_counts": dict(sorted(command_category_counts.items())),
        "file_change_category_counts": dict(sorted(file_change_category_counts.items())),
        "first_source_edit_item": first_source_edit,
        "first_test_command_item": first_test_command,
        "first_verification_command_item": first_verification_command,
        "first_audit_artifact_write_item": first_audit_artifact,
        "first_skill_proof_write_item": first_skill_proof,
        "items_after_first_source_edit": items_after(first_source_edit),
        "items_after_first_test_command": items_after(first_test_command),
        "items_after_first_audit_artifact_write": items_after(first_audit_artifact),
        "provider_item_timeline_note": "observed_from_codex_item_stream",
    }


def _summarize_rows(
    rows: list[dict[str, Any]],
    *,
    run_id: str,
    phase: str,
    provider: str,
    runner: str,
    trace_source: str,
    trace_fidelity: str,
    repo_root: Path | None,
    arm_slug: str,
) -> dict[str, Any]:
    turns_observed = _turns_from_rows(rows)
    assistant_messages_observed = sum(1 for row in rows if row.get("event_kind") == "assistant_message")
    tool_uses_observed = sum(1 for row in rows if row.get("event_kind") == "tool_use")
    file_changing_tool_uses_observed = sum(
        1 for row in rows if row.get("event_kind") == "tool_use" and row.get("file_changing_tool") is True
    )
    checkpoints_observed = sum(1 for row in rows if row.get("event_kind") == "checkpoint")
    checkpoint_rows = [row for row in rows if row.get("event_kind") == "checkpoint"]
    provider_item_summary = _summarize_provider_items(rows)
    file_changing_tool_uses_observed += int(provider_item_summary.get("file_change_items_observed") or 0)

    first_functional_green_turn: int | None = None
    first_functional_green_wall_seconds: float | None = None
    first_bench_ready_green_turn: int | None = None
    first_bench_ready_green_wall_seconds: float | None = None
    first_functional_green_item: int | None = None
    first_bench_ready_green_item: int | None = None
    permission_denials_after_first_green = 0
    first_green_turn: int | None = None

    for row in checkpoint_rows:
        provider_item_index = _coerce_int(row.get("provider_item_index"))
        if provider_item_index is not None:
            if row.get("functional_green") is True and first_functional_green_item is None:
                first_functional_green_item = provider_item_index
            if row.get("bench_ready_green") is True and first_bench_ready_green_item is None:
                first_bench_ready_green_item = provider_item_index
        turn_index = _coerce_int(row.get("turn_index"))
        if turn_index is None:
            continue
        wall_seconds = _coerce_float(row.get("wall_seconds"))
        if row.get("functional_green") is True and first_functional_green_turn is None:
            first_functional_green_turn = turn_index
            first_functional_green_wall_seconds = wall_seconds
            first_green_turn = turn_index
        if row.get("bench_ready_green") is True and first_bench_ready_green_turn is None:
            first_bench_ready_green_turn = turn_index
            first_bench_ready_green_wall_seconds = wall_seconds
        if first_functional_green_turn is not None and turn_index > first_functional_green_turn:
            permission_denials_after_first_green += _coerce_int(row.get("permission_denials_delta")) or 0

    turns_after_first_functional_green: int | None = None
    turns_after_first_bench_ready_green: int | None = None
    if turns_observed:
        if first_functional_green_turn is not None:
            turns_after_first_functional_green = max(turns_observed[-1] - first_functional_green_turn, 0)
        if first_bench_ready_green_turn is not None:
            turns_after_first_bench_ready_green = max(turns_observed[-1] - first_bench_ready_green_turn, 0)

    provider_items_observed = _coerce_int(provider_item_summary.get("provider_items_observed")) or 0
    items_after_first_functional_green = (
        max(provider_items_observed - first_functional_green_item, 0)
        if first_functional_green_item is not None and provider_items_observed
        else None
    )
    items_after_first_bench_ready_green = (
        max(provider_items_observed - first_bench_ready_green_item, 0)
        if first_bench_ready_green_item is not None and provider_items_observed
        else None
    )
    functional_to_bench_ready_items = (
        max(first_bench_ready_green_item - first_functional_green_item, 0)
        if first_functional_green_item is not None and first_bench_ready_green_item is not None
        else None
    )

    item_solution_latency_observable = bool(checkpoint_rows) and provider_items_observed > 0
    solution_latency_observable = item_solution_latency_observable or (
        trace_fidelity != TRACE_FIDELITY_RUN_LEVEL_ONLY
        and (first_functional_green_turn is not None or first_bench_ready_green_turn is not None)
    )
    if item_solution_latency_observable:
        solution_latency_source = "codex_workspace_snapshots"
        solution_latency_note = "observed_from_provider_item_checkpoints"
    else:
        solution_latency_source = _trace_source_for_solution_latency(trace_source, trace_fidelity)
        solution_latency_note = _solution_latency_note(trace_source, trace_fidelity, solution_latency_observable)

    skill_summary = _summarize_skill_evidence(repo_root, run_id=run_id, phase=phase, arm_slug=arm_slug)
    checkpoint_eval_errors = _flatten_checkpoint_errors(rows)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "phase": phase,
        "provider": provider,
        "runner": runner,
        "trace_source": trace_source,
        "trace_fidelity": trace_fidelity,
        "turns_observed": len(turns_observed),
        "assistant_messages_observed": assistant_messages_observed,
        "tool_uses_observed": tool_uses_observed,
        "file_changing_tool_uses_observed": file_changing_tool_uses_observed,
        "checkpoints_observed": checkpoints_observed,
        "checkpoint_count": checkpoints_observed,
        "first_green_turn": first_green_turn,
        "first_functional_green_turn": first_functional_green_turn,
        "first_functional_green_wall_seconds": first_functional_green_wall_seconds,
        "first_bench_ready_green_turn": first_bench_ready_green_turn,
        "first_bench_ready_green_wall_seconds": first_bench_ready_green_wall_seconds,
        "first_green_item": first_functional_green_item,
        "first_functional_green_item": first_functional_green_item,
        "first_bench_ready_green_item": first_bench_ready_green_item,
        "items_after_first_green": items_after_first_functional_green,
        "items_after_first_functional_green": items_after_first_functional_green,
        "items_after_first_bench_ready_green": items_after_first_bench_ready_green,
        "functional_to_bench_ready_items": functional_to_bench_ready_items,
        "item_solution_latency_observable": item_solution_latency_observable,
        "turns_after_first_green": turns_after_first_functional_green,
        "turns_after_first_functional_green": turns_after_first_functional_green,
        "turns_after_first_bench_ready_green": turns_after_first_bench_ready_green,
        "permission_denials_after_first_green": permission_denials_after_first_green,
        "solution_latency_observable": solution_latency_observable,
        "solution_latency_source": solution_latency_source,
        "solution_latency_note": solution_latency_note,
        "checkpoint_eval_errors": checkpoint_eval_errors,
        "raw_content_omitted": True,
        **provider_item_summary,
        **skill_summary,
    }

    if skill_summary.get("declared_events_by_turn"):
        summary["declared_events_by_turn"] = skill_summary["declared_events_by_turn"]
    if skill_summary.get("artifact_inferred_skills"):
        summary["artifact_inferred_skills"] = skill_summary["artifact_inferred_skills"]

    return summary


def _expand_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("events"), list):
        expanded = [item for item in payload["events"] if isinstance(item, dict)]
        if expanded:
            return expanded
    if isinstance(payload.get("event"), dict) and _safe_str(payload.get("type")) == "stream_event":
        return [payload["event"]]
    return [payload]


def parse_json_records(text: str) -> list[dict[str, Any]]:
    stripped_text = text.strip()
    if not stripped_text:
        return []

    try:
        payload = json.loads(stripped_text)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        records: list[dict[str, Any]] = []
        for item in _expand_payload(payload):
            if isinstance(item, dict):
                records.append(item)
        return records

    records: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            for item in _expand_payload(parsed):
                if isinstance(item, dict):
                    records.append(item)
    return records


def _record_codex_blocks(
    recorder: AgentTurnTraceRecorder,
    *,
    provider_event_type: str,
    turn_index: int | None,
    message_id: str | None,
    blocks: list[dict[str, Any]],
    wall_seconds: float | None,
) -> None:
    for block in blocks:
        block_type = _safe_str(block.get("type")) or ""
        if block_type != "tool_use":
            continue
        tool_use_id = _extract_tool_use_id(block)
        tool_name = _extract_tool_name(block)
        file_changing_tool = _is_file_changing_tool(tool_name)
        recorder.record_tool_use(
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            message_id=message_id,
            wall_seconds=wall_seconds,
            file_changing_tool=file_changing_tool,
            notes=["normalized from provider event"],
        )


def process_codex_record(
    recorder: AgentTurnTraceRecorder,
    raw_record: dict[str, Any],
    *,
    current_turn_index: int | None = None,
) -> int | None:
    provider_event_type = _safe_str(raw_record.get("type")) or _safe_str(raw_record.get("event_type")) or "unknown"
    event_type = provider_event_type.lower()
    normalized_event_type = event_type.replace(".", "_").replace("-", "_")
    turn_index = _extract_turn_index(raw_record)
    message_id = _extract_message_id(raw_record)
    wall_seconds = _extract_wall_seconds(raw_record)
    notes = ["normalized from codex jsonl/json", OBSERVED_NOTE]

    if normalized_event_type in {"item_started", "item_completed", "item_updated"}:
        item = _extract_item_payload(raw_record)
        item_turn_index = turn_index if turn_index is not None else current_turn_index
        if item is not None:
            item_type = _codex_item_type(item)
            item_id = _extract_tool_use_id(item)
            lifecycle = normalized_event_type.removeprefix("item_")
            command_category = _codex_command_category(item) if item_type == "command_execution" else None
            file_categories, audit_artifacts, path_count = (
                _codex_file_change_metadata(item) if item_type == "file_change" else ([], [], 0)
            )
            if item_type in {"agent_message", "command_execution", "file_change", "todo_list"}:
                recorder.record_provider_item(
                    provider_event_type=provider_event_type,
                    provider_item_type=item_type,
                    provider_item_lifecycle=lifecycle,
                    provider_item_status=_codex_item_status(item),
                    item_id=item_id,
                    turn_index=item_turn_index,
                    wall_seconds=wall_seconds,
                    command_category=command_category,
                    file_change_categories=file_categories,
                    audit_artifacts_changed=audit_artifacts,
                    paths_changed_count=path_count,
                    notes=notes,
                )

            if item_type == "command_execution":
                if lifecycle == "started" or not recorder.has_tool_use_id(item_id):
                    recorder.record_tool_use(
                        turn_index=item_turn_index,
                        provider_event_type=provider_event_type,
                        tool_use_id=item_id,
                        tool_name="command_execution",
                        message_id=message_id,
                        wall_seconds=wall_seconds,
                        file_changing_tool=False,
                        notes=notes,
                    )
                if lifecycle == "completed":
                    recorder.record_tool_result(
                        turn_index=item_turn_index,
                        provider_event_type=provider_event_type,
                        tool_use_id=item_id,
                        tool_name="command_execution",
                        message_id=message_id,
                        wall_seconds=wall_seconds,
                        file_changing_tool=False,
                        notes=notes,
                    )
                return item_turn_index

            if item_type == "file_change":
                if item_id not in recorder._file_change_observed_ids:
                    recorder.record_file_change_observed(
                        turn_index=item_turn_index,
                        provider_event_type=provider_event_type,
                        tool_use_id=item_id,
                        tool_name="file_change",
                        message_id=message_id,
                        wall_seconds=wall_seconds,
                        notes=["normalized from Codex file_change item", OBSERVED_NOTE],
                    )
                return item_turn_index

    if normalized_event_type in {"turn_started", "turn_start"}:
        turn_index = _resolve_codex_turn_index(
            current_turn_index,
            turn_index,
            start_new_turn=True,
            create_if_missing=True,
        )
        recorder.record_turn_started(
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            message_id=message_id,
            wall_seconds=wall_seconds,
            notes=notes,
        )
        return turn_index

    if normalized_event_type in {"assistant", "assistant_message", "message_start"}:
        if turn_index is None:
            turn_index = current_turn_index
        recorder.record_assistant_message(
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            message_id=message_id,
            wall_seconds=wall_seconds,
            notes=notes,
        )
        blocks = _extract_content_blocks(raw_record)
        _record_codex_blocks(
            recorder,
            provider_event_type=provider_event_type,
            turn_index=turn_index,
            message_id=message_id,
            blocks=blocks,
            wall_seconds=wall_seconds,
        )
        return turn_index

    if normalized_event_type in {"tool_use", "tool_call", "tool_requested", "tool_invocation"}:
        tool_use_id = _extract_tool_use_id(raw_record)
        tool_name = _extract_tool_name(raw_record)
        file_changing_tool = _coerce_bool(raw_record.get("file_changing_tool"))
        if file_changing_tool is None:
            file_changing_tool = _is_file_changing_tool(tool_name)
        recorder.record_tool_use(
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            message_id=message_id,
            wall_seconds=wall_seconds,
            file_changing_tool=file_changing_tool,
            notes=notes,
        )
        return turn_index

    if normalized_event_type in {"tool_result", "tool_output", "tool_response"}:
        tool_use_id = _extract_tool_use_id(raw_record)
        tool_name = _extract_tool_name(raw_record)
        file_changing_tool = _coerce_bool(raw_record.get("file_changing_tool"))
        recorder.record_tool_result(
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            message_id=message_id,
            wall_seconds=wall_seconds,
            file_changing_tool=file_changing_tool,
            notes=notes,
        )
        return turn_index

    if normalized_event_type == "item_completed":
        item = _extract_item_payload(raw_record)
        item_turn_index = turn_index if turn_index is not None else current_turn_index
        if item is None:
            return current_turn_index

        item_type = _codex_item_type(item)
        item_message_id = _extract_message_id(item) or message_id
        item_tool_use_id = _extract_tool_use_id(item)
        item_tool_name = _extract_tool_name(item)

        if item_type in {"tool_call", "tool_use", "tool_requested", "tool_invocation"}:
            file_changing_tool = _coerce_bool(item.get("file_changing_tool"))
            if file_changing_tool is None:
                file_changing_tool = _is_file_changing_tool(item_tool_name)
            recorder.record_tool_use(
                turn_index=item_turn_index,
                provider_event_type=provider_event_type,
                tool_use_id=item_tool_use_id,
                tool_name=item_tool_name,
                message_id=item_message_id,
                wall_seconds=wall_seconds,
                file_changing_tool=file_changing_tool,
                notes=notes,
            )
            blocks = _extract_content_blocks(item)
            _record_codex_blocks(
                recorder,
                provider_event_type=provider_event_type,
                turn_index=item_turn_index,
                message_id=item_message_id,
                blocks=blocks,
                wall_seconds=wall_seconds,
            )
            return item_turn_index

        if item_type in {"tool_result", "tool_output", "tool_response"}:
            file_changing_tool = _coerce_bool(item.get("file_changing_tool"))
            recorder.record_tool_result(
                turn_index=item_turn_index,
                provider_event_type=provider_event_type,
                tool_use_id=item_tool_use_id,
                tool_name=item_tool_name,
                message_id=item_message_id,
                wall_seconds=wall_seconds,
                file_changing_tool=file_changing_tool,
                notes=notes,
            )
            return item_turn_index

        if item_type in {"agent_message", "assistant_message", "message"}:
            recorder.record_assistant_message(
                turn_index=item_turn_index,
                provider_event_type=provider_event_type,
                message_id=item_message_id,
                wall_seconds=wall_seconds,
                notes=notes,
            )
            blocks = _extract_content_blocks(item)
            _record_codex_blocks(
                recorder,
                provider_event_type=provider_event_type,
                turn_index=item_turn_index,
                message_id=item_message_id,
                blocks=blocks,
                wall_seconds=wall_seconds,
            )
            return item_turn_index

    if normalized_event_type in {"turn_completed", "turn_end", "message_stop"}:
        turn_index = _resolve_codex_turn_index(
            current_turn_index,
            turn_index,
            create_if_missing=True,
        )
        recorder.record_turn_completed(
            turn_index=turn_index,
            provider_event_type=provider_event_type,
            message_id=message_id,
            wall_seconds=wall_seconds,
            notes=notes,
        )
        return turn_index

    if normalized_event_type in {"result", "run_result", "final_result"}:
        recorder.record_run_result(
            provider_event_type=provider_event_type,
            wall_seconds=wall_seconds,
            turn_index=turn_index,
            exit_code=_extract_exit_code(raw_record),
            notes=notes,
        )
        return turn_index

    if normalized_event_type in {"error", "provider_error"}:
        recorder.record_provider_error(
            provider_event_type=provider_event_type,
            wall_seconds=wall_seconds,
            turn_index=turn_index,
            notes=notes,
        )
        return turn_index

    return current_turn_index


def summarize_codex_records(
    text: str,
    *,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    repo_root: Path | None = None,
    provider: str = PROVIDER_CODEX,
    runner: str = "codex-cli",
    trace_source: str = TRACE_SOURCE_CODEX_JSONL,
    trace_fidelity: str = TRACE_FIDELITY_RUN_LEVEL_ONLY,
    jsonl_path: Path | None = None,
    summary_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records = parse_json_records(text)
    recorder = AgentTurnTraceRecorder(
        run_id=run_id,
        task_slug=task_slug,
        arm_slug=arm_slug,
        phase=phase,
        provider=provider,
        runner=runner,
        trace_source=trace_source,
        trace_fidelity=trace_fidelity,
        repo_root=repo_root,
        jsonl_path=jsonl_path,
        summary_path=summary_path,
    )
    if jsonl_path is not None:
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        jsonl_path.write_text("", encoding="utf-8")

    current_turn_index: int | None = None
    for record in records:
        current_turn_index = process_codex_record(recorder, record, current_turn_index=current_turn_index)

    summary = recorder.build_summary()
    return _flatten_event_rows(recorder.rows), summary


def write_trace_artifacts(
    recorder: AgentTurnTraceRecorder,
    *,
    summary_only: bool = False,
) -> dict[str, Any]:
    if not summary_only and recorder.jsonl_path is not None:
        recorder.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    return recorder.build_summary()


def read_trace_summary(path: str | Path) -> dict[str, Any] | None:
    summary = _read_json(Path(path))
    return summary if summary is not None else None


def normalize_codex_trace_file(
    input_path: str | Path,
    out_dir: str | Path,
    *,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    repo_root: str | Path | None = None,
    provider: str = PROVIDER_CODEX,
    runner: str = "codex-cli",
    trace_source: str = TRACE_SOURCE_CODEX_JSONL,
    trace_fidelity: str = TRACE_FIDELITY_RUN_LEVEL_ONLY,
) -> dict[str, Any]:
    source_path = Path(input_path)
    output_dir = Path(out_dir)
    text = source_path.read_text(encoding="utf-8", errors="replace") if source_path.exists() else ""
    _, summary = summarize_codex_records(
        text,
        run_id=run_id,
        task_slug=task_slug,
        arm_slug=arm_slug,
        phase=phase,
        repo_root=Path(repo_root) if repo_root is not None else None,
        provider=provider,
        runner=runner,
        trace_source=trace_source,
        trace_fidelity=trace_fidelity,
        jsonl_path=output_dir / TRACE_FILENAME,
        summary_path=output_dir / TRACE_SUMMARY_FILENAME,
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize provider turn traces into safe benchmark artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    codex = subparsers.add_parser("summarize-codex", help="Normalize Codex stdout into agent_turn_trace artifacts.")
    codex.add_argument("--input", required=True, help="Path to Codex stdout, or - for stdin.")
    codex.add_argument("--out-dir", required=True, type=Path)
    codex.add_argument("--run-id", required=True)
    codex.add_argument("--task-slug", required=True)
    codex.add_argument("--arm-slug", required=True)
    codex.add_argument("--phase", required=True)
    codex.add_argument("--repo-root", default=None)
    codex.add_argument("--provider", default=PROVIDER_CODEX)
    codex.add_argument("--runner", default="codex-cli")
    codex.add_argument("--trace-source", default=TRACE_SOURCE_CODEX_JSONL)
    codex.add_argument("--trace-fidelity", default=TRACE_FIDELITY_RUN_LEVEL_ONLY)

    args = parser.parse_args(argv)

    if args.command == "summarize-codex":
        input_text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8", errors="replace")
        _, summary = summarize_codex_records(
            input_text,
            run_id=args.run_id,
            task_slug=args.task_slug,
            arm_slug=args.arm_slug,
            phase=args.phase,
            repo_root=Path(args.repo_root) if args.repo_root else None,
            provider=args.provider,
            runner=args.runner,
            trace_source=args.trace_source,
            trace_fidelity=args.trace_fidelity,
            jsonl_path=args.out_dir / TRACE_FILENAME,
            summary_path=args.out_dir / TRACE_SUMMARY_FILENAME,
        )
        print(args.out_dir / TRACE_SUMMARY_FILENAME)
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
