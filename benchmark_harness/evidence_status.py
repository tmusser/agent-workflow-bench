from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

_BOOL_TEXT = {
    "true": True,
    "false": False,
    "1": True,
    "0": False,
    "yes": True,
    "no": False,
    "pass": True,
    "passed": True,
    "fail": False,
    "failed": False,
}

_VERIFY_EXPLICIT_PATTERNS = (
    r"\bverify(?:ication)?(?:_|-|\s)*exit(?:_|-|\s)*(?:code)?\s*[:=]\s*(0|1)\b",
    r"\bverify_exit\s*[:=]\s*(0|1)\b",
    r"\bverification_exit\s*[:=]\s*(0|1)\b",
)
_HIDDEN_EXPLICIT_PATTERNS = (
    r"\bhidden(?:_|-|\s)*evaluator(?:_|-|\s)*exit(?:_|-|\s)*(?:code)?\s*[:=]\s*(0|1)\b",
    r"\bhidden_evaluator_exit\s*[:=]\s*(0|1)\b",
)


def _coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    return _BOOL_TEXT.get(str(value).strip().lower())


def _structured_mapping(text: str) -> dict[str, object]:
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    mapping: dict[str, object] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        key, raw = match.groups()
        boolean = _coerce_bool(raw)
        mapping[key] = boolean if boolean is not None else raw
    return mapping


def _explicit_exit(text: str, kind: str) -> int | None:
    patterns = _VERIFY_EXPLICIT_PATTERNS if kind == "verify" else _HIDDEN_EXPLICIT_PATTERNS
    lowered = text.lower()
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            return int(match.group(1))
    return None


def _structured_exit(text: str, kind: str) -> int | None:
    data = _structured_mapping(text)
    if not data:
        return None

    if kind == "verify":
        for key in ("public_verify_exit_code", "public_verify_exit", "verify_exit", "verification_exit"):
            value = data.get(key)
            if value in (0, 1, "0", "1"):
                return int(value)
        for key in ("public_verify_green", "verification_green", "verify_green"):
            value = _coerce_bool(data.get(key))
            if value is not None:
                return 0 if value else 1
        return None

    overall = _coerce_bool(data.get("overall_green"))
    if overall is not None:
        return 0 if overall else 1

    task6_keys = ("fresh_review_present", "resume_request_complete", "hidden_contract_pass")
    if all(key in data for key in task6_keys):
        values = [_coerce_bool(data.get(key)) for key in task6_keys]
        if all(value is not None for value in values):
            return 0 if all(values) else 1

    hidden_contract = _coerce_bool(data.get("hidden_contract_pass"))
    if hidden_contract is not None:
        errors = data.get("errors")
        if isinstance(errors, list) and errors:
            return 1
        return 0 if hidden_contract else 1

    errors = data.get("errors")
    if isinstance(errors, list):
        return 1 if errors else None
    return None


def infer_exit_from_text(text: str, kind: str) -> int | None:
    if kind not in {"verify", "hidden"}:
        raise ValueError(f"unknown evaluator kind: {kind}")

    explicit = _explicit_exit(text, kind)
    if explicit is not None:
        return explicit

    structured = _structured_exit(text, kind)
    if structured is not None:
        return structured

    lowered = text.lower()
    if kind == "verify":
        fail_markers = (
            "traceback (most recent call last)",
            "assertionerror",
            "failed tests",
            "test session fails",
        )
        fail_regexes = (
            r"^failed\b",
            r"\b[1-9]\d*\s+failed\b",
            r"^error\b",
            r"\b[1-9]\d*\s+errors?\b",
        )
        pass_markers = (
            "passed in",
            "all tests passed",
            "no impossible churn detected",
            "verification passed",
            "verify.sh passed",
        )
    else:
        fail_markers = (
            "traceback (most recent call last)",
            "assertionerror",
            "hidden contract failed",
        )
        fail_regexes = (
            r"^failed\b",
            r"\b[1-9]\d*\s+failed\b",
            r"^error\b",
            r"\b[1-9]\d*\s+errors?\b",
        )
        pass_markers = (
            "hidden task 4 evaluator passed",
            "no hidden contract failed",
            "evaluator passed",
        )
        if "no hidden contract failed" in lowered:
            return 0

    if any(marker in lowered for marker in fail_markers):
        return 1
    if any(re.search(pattern, lowered, flags=re.MULTILINE) for pattern in fail_regexes):
        return 1
    if any(marker in lowered for marker in pass_markers):
        return 0
    return None


def infer_command_exit(paths: Iterable[Path], kind: str) -> int | None:
    texts: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        explicit = _explicit_exit(text, kind)
        if explicit is not None:
            return explicit
        structured = _structured_exit(text, kind)
        if structured is not None:
            return structured
        texts.append(text)

    for text in texts:
        inferred = infer_exit_from_text(text, kind)
        if inferred is not None:
            return inferred
    return None
