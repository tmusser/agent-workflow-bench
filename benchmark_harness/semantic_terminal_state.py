from __future__ import annotations

import re

DONE_VERIFIED = "done_verified"
DONE_UNVERIFIED = "done_unverified"
ASKS_PERMISSION_TO_VERIFY = "asks_permission_to_verify"
MAX_TURNS_AFTER_CORRECT_FIX = "max_turns_after_correct_fix"
MAX_TURNS_BEFORE_CORRECT_FIX = "max_turns_before_correct_fix"
WRONG_FIX = "wrong_fix"
NO_DIFF = "no_diff"
NOT_RUN = "not_run"
UNKNOWN = "unknown"

SEMANTIC_TERMINAL_STATES = {
    DONE_VERIFIED,
    DONE_UNVERIFIED,
    ASKS_PERMISSION_TO_VERIFY,
    MAX_TURNS_AFTER_CORRECT_FIX,
    MAX_TURNS_BEFORE_CORRECT_FIX,
    WRONG_FIX,
    NO_DIFF,
    NOT_RUN,
    UNKNOWN,
}

_PERMISSION_VERIFY_PATTERNS = [
    r"\b(can|could|may|should)\s+i\s+(run|execute)\b.{0,80}\b(verify|verification|pytest|tests?)\b",
    r"\bplease\s+(allow|approve|permit)\b.{0,80}\b(verify|verification|pytest|tests?)\b",
    r"\bneed\s+(permission|approval)\b.{0,80}\b(verify|verification|pytest|tests?)\b",
    r"\bwaiting\s+for\s+(permission|approval)\b.{0,80}\b(verify|verification|pytest|tests?)\b",
]

_VERIFIED_MARKERS = [
    "ran verify.sh",
    "ran verify",
    "ran pytest",
    "ran tests",
    "i ran",
    "i verified",
    "verified by",
    "verification passed",
    "verify.sh passed",
    "tests passed",
]


def _is_green(verify_exit: object, hidden_exit: object) -> bool:
    return verify_exit == 0 and hidden_exit == 0


def _asks_permission_to_verify(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered, flags=re.DOTALL) for pattern in _PERMISSION_VERIFY_PATTERNS)


def _claims_verification(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _VERIFIED_MARKERS)


def classify_semantic_terminal_state(
    *,
    terminal_reason: str | None,
    verify_exit: object,
    hidden_exit: object,
    diff_bytes: int,
    text: str = "",
) -> str:
    """Classify an agent run by what the final workspace/output semantically means.

    This deliberately separates functional correctness from the raw CLI terminal
    status. A run can hit ``max_turns`` after leaving a patch that passes both
    public and hidden checks, and a run can report ``completed`` while merely
    asking for permission to verify.
    """

    normalized_terminal = (terminal_reason or "").strip().lower()
    green = _is_green(verify_exit, hidden_exit)
    asks_permission = _asks_permission_to_verify(text)

    if verify_exit == "not_run" or hidden_exit == "not_run":
        return NOT_RUN

    if green:
        if asks_permission:
            return ASKS_PERMISSION_TO_VERIFY
        if normalized_terminal == "max_turns":
            return MAX_TURNS_AFTER_CORRECT_FIX
        if _claims_verification(text):
            return DONE_VERIFIED
        return DONE_UNVERIFIED

    if diff_bytes <= 0:
        return NO_DIFF

    if asks_permission:
        return ASKS_PERMISSION_TO_VERIFY

    if normalized_terminal == "max_turns":
        return MAX_TURNS_BEFORE_CORRECT_FIX

    if verify_exit == 1 or hidden_exit == 1:
        return WRONG_FIX

    return UNKNOWN
