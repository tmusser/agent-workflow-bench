from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LATENCY_NOT_OBSERVABLE = "not_observable"
LATENCY_PHASE_NOT_RUN = "phase_not_run"


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
            parsed = int(value)
        except ValueError:
            return None
        return parsed
    return None


def _actual_turns(run_dir: Path) -> int | None:
    metrics = _read_json(run_dir / "run_metrics.json") or {}
    return _coerce_int(metrics.get("actual_turns"))


def _is_green_event(event: dict[str, Any]) -> bool:
    if event.get("green") is True or event.get("public_hidden_green") is True:
        return True
    verify_exit = event.get("verify_exit", event.get("verification_exit"))
    hidden_exit = event.get("hidden_exit", event.get("hidden_evaluator_exit"))
    return _coerce_int(verify_exit) == 0 and _coerce_int(hidden_exit) == 0


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


def _summarize_events(events: list[dict[str, Any]], actual_turns: int | None, source: str) -> dict[str, Any] | None:
    first_green_turn: int | None = None
    permission_denials_after_first_green = 0

    for event in events:
        turn = _coerce_int(event.get("turn", event.get("turn_index")))
        if turn is None:
            continue
        if first_green_turn is None and _is_green_event(event):
            first_green_turn = turn
            continue
        if first_green_turn is not None and turn > first_green_turn:
            permission_denials_after_first_green += _permission_denials_in_event(event)

    if first_green_turn is None:
        return None

    turns_after_first_green = None
    if actual_turns is not None:
        turns_after_first_green = max(actual_turns - first_green_turn, 0)

    return {
        "solution_latency_observable": True,
        "actual_turns": actual_turns,
        "first_green_turn": first_green_turn,
        "turns_after_first_green": turns_after_first_green,
        "permission_denials_after_first_green": permission_denials_after_first_green,
        "solution_latency_source": source,
        "solution_latency_note": "observed_from_per_turn_trace",
    }


def _explicit_solution_latency(run_dir: Path, actual_turns: int | None) -> dict[str, Any] | None:
    data = _read_json(run_dir / "solution_latency.json")
    if not data:
        return None

    first_green_turn = _coerce_int(data.get("first_green_turn"))
    if first_green_turn is None:
        return None

    explicit_actual_turns = _coerce_int(data.get("actual_turns"))
    actual_turns = explicit_actual_turns if explicit_actual_turns is not None else actual_turns

    turns_after_first_green = _coerce_int(data.get("turns_after_first_green"))
    if turns_after_first_green is None and actual_turns is not None:
        turns_after_first_green = max(actual_turns - first_green_turn, 0)

    permission_denials_after_first_green = _coerce_int(data.get("permission_denials_after_first_green"))

    return {
        "solution_latency_observable": True,
        "actual_turns": actual_turns,
        "first_green_turn": first_green_turn,
        "turns_after_first_green": turns_after_first_green,
        "permission_denials_after_first_green": permission_denials_after_first_green,
        "solution_latency_source": "solution_latency.json",
        "solution_latency_note": str(data.get("note") or "observed_from_solution_latency_summary"),
    }


def summarize_solution_latency(run_dir: Path, *, verify_exit: object, hidden_exit: object) -> dict[str, Any]:
    """Summarize first-green-turn evidence for a run directory.

    Existing bundles usually do not contain per-turn workspace/evaluator traces, so
    first-green turn must remain unknown. Future bundles can opt in by including
    either `solution_latency.json`, `solution_timeline.jsonl`, or `turn_events.jsonl`.
    """

    actual_turns = _actual_turns(run_dir)

    if verify_exit == "not_run" or hidden_exit == "not_run":
        return {
            "solution_latency_observable": False,
            "actual_turns": actual_turns,
            "first_green_turn": None,
            "turns_after_first_green": None,
            "permission_denials_after_first_green": None,
            "solution_latency_source": "",
            "solution_latency_note": LATENCY_PHASE_NOT_RUN,
        }

    explicit = _explicit_solution_latency(run_dir, actual_turns)
    if explicit is not None:
        return explicit

    for filename in ("solution_timeline.jsonl", "turn_events.jsonl"):
        summary = _summarize_events(_parse_jsonl_events(run_dir / filename), actual_turns, filename)
        if summary is not None:
            return summary

    return {
        "solution_latency_observable": False,
        "actual_turns": actual_turns,
        "first_green_turn": None,
        "turns_after_first_green": None,
        "permission_denials_after_first_green": None,
        "solution_latency_source": "",
        "solution_latency_note": LATENCY_NOT_OBSERVABLE,
    }
