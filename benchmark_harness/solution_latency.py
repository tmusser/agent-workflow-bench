from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark_harness.agent_turn_trace import TRACE_SUMMARY_FILENAME

LATENCY_NOT_OBSERVABLE = "not_observable"
LATENCY_PHASE_NOT_RUN = "phase_not_run"
LATENCY_FINAL_ONLY = "final_only_no_per_turn_trace"
LATENCY_OBSERVED_STREAM = "stream_json"
LATENCY_OBSERVED_MTIME = "mtime_polling"
LATENCY_OBSERVED_TRACE_NOTE = "observed_from_per_turn_trace"
LATENCY_OBSERVED_MTIME_NOTE = "observed_from_mtime_polling"


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


def _actual_turns(run_dir: Path) -> int | None:
    metrics = _read_json(run_dir / "run_metrics.json") or {}
    return _coerce_int(metrics.get("actual_turns") or metrics.get("num_turns") or metrics.get("final_turns"))


def _final_green_from_exits(verify_exit: object, hidden_exit: object) -> bool:
    return _coerce_int(verify_exit) == 0 and _coerce_int(hidden_exit) == 0


def _event_turn(event: dict[str, Any], fallback_turn: int | None = None) -> int | None:
    turn = _coerce_int(event.get("turn", event.get("turn_index")))
    if turn is not None:
        return turn
    return fallback_turn


def _event_wall_seconds(event: dict[str, Any]) -> float | None:
    for key in ("wall_seconds", "wall_clock_seconds", "elapsed_seconds", "duration_seconds"):
        value = _coerce_float(event.get(key))
        if value is not None:
            return value
    return None


def _event_functional_green(event: dict[str, Any]) -> bool:
    if (explicit := _coerce_bool(event.get("functional_green"))) is not None:
        return explicit
    if (explicit := _coerce_bool(event.get("public_hidden_green"))) is not None:
        return explicit
    verify_exit = event.get("verify_exit", event.get("verification_exit"))
    hidden_exit = event.get("hidden_exit", event.get("hidden_evaluator_exit"))
    return _final_green_from_exits(verify_exit, hidden_exit)


def _event_bench_ready_green(event: dict[str, Any]) -> bool:
    if (explicit := _coerce_bool(event.get("bench_ready_green"))) is not None:
        return explicit
    if (explicit := _coerce_bool(event.get("bench_ready"))) is not None:
        return explicit
    return _event_functional_green(event)


def _permission_denials_in_event(event: dict[str, Any]) -> int:
    for key in (
        "permission_denials_delta",
        "permission_denials_count_delta",
        "permission_denied_count",
        "permission_denials",
    ):
        value = _coerce_int(event.get(key))
        if value is not None:
            return max(value, 0)

    if event.get("permission_denied") is True:
        return 1

    event_name = str(event.get("event", "")).lower()
    message = str(event.get("message", "")).lower()
    if "permission" in event_name and "denied" in event_name:
        return 1
    if "permission" in message and "denied" in message:
        return 1
    return 0


def _checkpoint_errors(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in (
        "checkpoint_error",
        "checkpoint_eval_error",
        "error",
    ):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            errors.append(value.strip())

    list_value = event.get("checkpoint_eval_errors")
    if isinstance(list_value, list):
        for item in list_value:
            if isinstance(item, str) and item.strip():
                errors.append(item.strip())
            elif item is not None:
                errors.append(str(item))

    if isinstance(event.get("errors"), list):
        for item in event["errors"]:
            if isinstance(item, str) and item.strip():
                errors.append(item.strip())
            elif item is not None:
                errors.append(str(item))

    return errors


def _parse_jsonl_events(path: Path) -> list[dict[str, Any]]:
    text = _read_text(path)
    if text is None:
        return []

    events = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def _event_source(events: list[dict[str, Any]], explicit_source: str | None = None) -> str:
    if explicit_source:
        return explicit_source
    for event in events:
        source = event.get("source")
        if isinstance(source, str) and source.strip():
            return source.strip()
    if events:
        return LATENCY_OBSERVED_STREAM
    return LATENCY_FINAL_ONLY


def _source_note(source: str, observed: bool) -> str:
    if source == LATENCY_OBSERVED_MTIME:
        return LATENCY_OBSERVED_MTIME_NOTE
    if observed:
        return LATENCY_OBSERVED_TRACE_NOTE
    if source:
        return LATENCY_NOT_OBSERVABLE
    return LATENCY_NOT_OBSERVABLE


def _normalize_checkpoint_errors(errors: list[str] | None) -> list[str]:
    if not errors:
        return []
    return [error for error in errors if error]


def _summarize_events(
    events: list[dict[str, Any]],
    actual_turns: int | None,
    source: str,
) -> dict[str, Any] | None:
    if not events:
        return None

    first_functional_turn: int | None = None
    first_functional_wall_seconds: float | None = None
    first_bench_ready_turn: int | None = None
    first_bench_ready_wall_seconds: float | None = None
    permission_denials_after_first_functional_green = 0
    checkpoint_errors: list[str] = []

    for fallback_turn, event in enumerate(events, start=1):
        turn = _event_turn(event, fallback_turn)
        if turn is None:
            continue

        wall_seconds = _event_wall_seconds(event)
        functional_green = _event_functional_green(event)
        bench_ready_green = _event_bench_ready_green(event)

        if first_functional_turn is None and functional_green:
            first_functional_turn = turn
            first_functional_wall_seconds = wall_seconds

        if first_bench_ready_turn is None and bench_ready_green:
            first_bench_ready_turn = turn
            first_bench_ready_wall_seconds = wall_seconds

        if first_functional_turn is not None and turn > first_functional_turn:
            permission_denials_after_first_functional_green += _permission_denials_in_event(event)

        checkpoint_errors.extend(_checkpoint_errors(event))

    turns_after_first_functional_green = None
    turns_after_first_bench_ready_green = None
    if actual_turns is not None:
        if first_functional_turn is not None:
            turns_after_first_functional_green = max(actual_turns - first_functional_turn, 0)
        if first_bench_ready_turn is not None:
            turns_after_first_bench_ready_green = max(actual_turns - first_bench_ready_turn, 0)

    observed = True
    source = source or LATENCY_OBSERVED_STREAM
    note = _source_note(source, observed)

    result = {
        "observable": observed,
        "solution_latency_observable": observed,
        "source": source,
        "solution_latency_source": source,
        "note": note,
        "solution_latency_note": note,
        "actual_turns": actual_turns,
        "final_turns": actual_turns,
        "final_green": None,
        "first_green_turn": first_functional_turn,
        "first_functional_green_turn": first_functional_turn,
        "first_functional_green_wall_seconds": first_functional_wall_seconds,
        "first_bench_ready_green_turn": first_bench_ready_turn,
        "first_bench_ready_green_wall_seconds": first_bench_ready_wall_seconds,
        "turns_after_first_green": turns_after_first_functional_green,
        "turns_after_first_functional_green": turns_after_first_functional_green,
        "turns_after_first_bench_ready_green": turns_after_first_bench_ready_green,
        "permission_denials_after_first_green": permission_denials_after_first_functional_green,
        "checkpoint_count": len(events),
        "checkpoint_eval_errors": _normalize_checkpoint_errors(checkpoint_errors),
    }
    return result


def _explicit_solution_latency(
    run_dir: Path,
    actual_turns: int | None,
    *,
    verify_exit: object,
    hidden_exit: object,
) -> dict[str, Any] | None:
    for filename in ("solution_latency.json", TRACE_SUMMARY_FILENAME):
        data = _read_json(run_dir / filename)
        if data:
            return _explicit_solution_latency_from_data(
                data,
                actual_turns,
                verify_exit=verify_exit,
                hidden_exit=hidden_exit,
            )
    return None


def _explicit_solution_latency_from_data(
    data: dict[str, Any],
    actual_turns: int | None,
    *,
    verify_exit: object,
    hidden_exit: object,
) -> dict[str, Any] | None:
    if not data:
        return None

    explicit_actual_turns = _coerce_int(data.get("actual_turns") or data.get("final_turns") or data.get("num_turns"))
    actual_turns = explicit_actual_turns if explicit_actual_turns is not None else actual_turns

    first_functional_turn = _coerce_int(
        data.get("first_functional_green_turn")
        if data.get("first_functional_green_turn") is not None
        else data.get("first_green_turn")
    )
    first_bench_ready_turn = _coerce_int(data.get("first_bench_ready_green_turn"))

    turns_after_first_functional_green = _coerce_int(
        data.get("turns_after_first_functional_green")
        if data.get("turns_after_first_functional_green") is not None
        else data.get("turns_after_first_green")
    )
    turns_after_first_bench_ready_green = _coerce_int(data.get("turns_after_first_bench_ready_green"))

    source = data.get("source") or data.get("solution_latency_source")
    if not isinstance(source, str) or not source.strip():
        source = LATENCY_FINAL_ONLY if not _coerce_bool(data.get("solution_latency_observable") or data.get("observable")) else LATENCY_OBSERVED_STREAM
    source = source.strip()

    observable = _coerce_bool(data.get("solution_latency_observable"))
    if observable is None:
        observable = _coerce_bool(data.get("observable"))
    if observable is None:
        observable = first_functional_turn is not None or first_bench_ready_turn is not None or source in {
            LATENCY_OBSERVED_STREAM,
            LATENCY_OBSERVED_MTIME,
        }

    if observable and turns_after_first_functional_green is None and first_functional_turn is not None and actual_turns is not None:
        turns_after_first_functional_green = max(actual_turns - first_functional_turn, 0)
    if observable and turns_after_first_bench_ready_green is None and first_bench_ready_turn is not None and actual_turns is not None:
        turns_after_first_bench_ready_green = max(actual_turns - first_bench_ready_turn, 0)

    checkpoint_eval_errors = data.get("checkpoint_eval_errors")
    if isinstance(checkpoint_eval_errors, list):
        checkpoint_errors = [str(item) for item in checkpoint_eval_errors if item is not None]
    elif isinstance(checkpoint_eval_errors, str) and checkpoint_eval_errors.strip():
        checkpoint_errors = [checkpoint_eval_errors.strip()]
    else:
        checkpoint_errors = []

    note = data.get("note") or data.get("solution_latency_note")
    if not isinstance(note, str) or not note.strip():
        note = _source_note(source, observable)
    note = note.strip()

    final_green = _final_green_from_exits(verify_exit, hidden_exit)
    final_turns = actual_turns

    return {
        "observable": observable,
        "solution_latency_observable": observable,
        "source": source,
        "solution_latency_source": source,
        "note": note,
        "solution_latency_note": note,
        "actual_turns": actual_turns,
        "final_turns": final_turns,
        "final_green": final_green,
        "first_green_turn": first_functional_turn,
        "first_functional_green_turn": first_functional_turn,
        "first_functional_green_wall_seconds": _coerce_float(data.get("first_functional_green_wall_seconds")),
        "first_bench_ready_green_turn": first_bench_ready_turn,
        "first_bench_ready_green_wall_seconds": _coerce_float(data.get("first_bench_ready_green_wall_seconds")),
        "turns_after_first_green": turns_after_first_functional_green,
        "turns_after_first_functional_green": turns_after_first_functional_green,
        "turns_after_first_bench_ready_green": turns_after_first_bench_ready_green,
        "permission_denials_after_first_green": _coerce_int(data.get("permission_denials_after_first_green")),
        "checkpoint_count": _coerce_int(data.get("checkpoint_count")) or 0,
        "checkpoint_eval_errors": checkpoint_errors,
    }


def summarize_solution_latency(run_dir: Path, *, verify_exit: object, hidden_exit: object) -> dict[str, Any]:
    """Summarize first-green evidence for a run directory.

    Existing bundles may still lack per-turn traces. In that case the summary is
    final-only and marked unobservable. When turn checkpoints are available, the
    summary records the first functional and bench-ready green checkpoints.
    """

    actual_turns = _actual_turns(run_dir)
    final_green = _final_green_from_exits(verify_exit, hidden_exit)

    if verify_exit == "not_run" or hidden_exit == "not_run":
        return {
            "observable": False,
            "solution_latency_observable": False,
            "source": "",
            "solution_latency_source": "",
            "note": LATENCY_PHASE_NOT_RUN,
            "solution_latency_note": LATENCY_PHASE_NOT_RUN,
            "actual_turns": actual_turns,
            "final_turns": actual_turns,
            "final_green": False,
            "first_green_turn": None,
            "first_functional_green_turn": None,
            "first_functional_green_wall_seconds": None,
            "first_bench_ready_green_turn": None,
            "first_bench_ready_green_wall_seconds": None,
            "turns_after_first_green": None,
            "turns_after_first_functional_green": None,
            "turns_after_first_bench_ready_green": None,
            "permission_denials_after_first_green": None,
            "checkpoint_count": 0,
            "checkpoint_eval_errors": [],
        }

    explicit = _explicit_solution_latency(run_dir, actual_turns, verify_exit=verify_exit, hidden_exit=hidden_exit)
    if explicit is not None:
        explicit["final_green"] = final_green
        if explicit.get("final_turns") is None:
            explicit["final_turns"] = actual_turns
        return explicit

    for filename in ("solution_timeline.jsonl", "turn_events.jsonl"):
        events = _parse_jsonl_events(run_dir / filename)
        if not events:
            continue
        source = _event_source(events)
        summary = _summarize_events(events, actual_turns, source)
        if summary is not None:
            summary["final_green"] = final_green
            return summary

    return {
        "observable": False,
        "solution_latency_observable": False,
        "source": LATENCY_FINAL_ONLY,
        "solution_latency_source": LATENCY_FINAL_ONLY,
        "note": LATENCY_NOT_OBSERVABLE,
        "solution_latency_note": LATENCY_NOT_OBSERVABLE,
        "actual_turns": actual_turns,
        "final_turns": actual_turns,
        "final_green": final_green,
        "first_green_turn": None,
        "first_functional_green_turn": None,
        "first_functional_green_wall_seconds": None,
        "first_bench_ready_green_turn": None,
        "first_bench_ready_green_wall_seconds": None,
        "turns_after_first_green": None,
        "turns_after_first_functional_green": None,
        "turns_after_first_bench_ready_green": None,
        "permission_denials_after_first_green": None,
        "checkpoint_count": 0,
        "checkpoint_eval_errors": [],
    }
