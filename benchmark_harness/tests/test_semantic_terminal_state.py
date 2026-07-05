from __future__ import annotations

from benchmark_harness.semantic_terminal_state import (
    ASKS_PERMISSION_TO_VERIFY,
    DONE_UNVERIFIED,
    DONE_VERIFIED,
    MAX_TURNS_AFTER_CORRECT_FIX,
    MAX_TURNS_BEFORE_CORRECT_FIX,
    NO_DIFF,
    NOT_RUN,
    WRONG_FIX,
    classify_semantic_terminal_state,
)


def test_semantic_terminal_state_detects_done_verified():
    assert (
        classify_semantic_terminal_state(
            terminal_reason="completed",
            verify_exit=0,
            hidden_exit=0,
            diff_bytes=128,
            text="I ran VERIFY.sh and pytest -q; tests passed.",
        )
        == DONE_VERIFIED
    )


def test_semantic_terminal_state_detects_completed_but_asking_to_verify():
    assert (
        classify_semantic_terminal_state(
            terminal_reason="completed",
            verify_exit=0,
            hidden_exit=0,
            diff_bytes=128,
            text="The fix is in place. May I run VERIFY.sh to confirm?",
        )
        == ASKS_PERMISSION_TO_VERIFY
    )


def test_semantic_terminal_state_detects_max_turns_after_correct_fix():
    assert (
        classify_semantic_terminal_state(
            terminal_reason="max_turns",
            verify_exit=0,
            hidden_exit=0,
            diff_bytes=128,
            text="Implemented the fix.",
        )
        == MAX_TURNS_AFTER_CORRECT_FIX
    )


def test_semantic_terminal_state_detects_max_turns_before_correct_fix():
    assert (
        classify_semantic_terminal_state(
            terminal_reason="max_turns",
            verify_exit=0,
            hidden_exit=1,
            diff_bytes=128,
            text="Still debugging the hidden evaluator.",
        )
        == MAX_TURNS_BEFORE_CORRECT_FIX
    )


def test_semantic_terminal_state_detects_wrong_fix():
    assert (
        classify_semantic_terminal_state(
            terminal_reason="completed",
            verify_exit=0,
            hidden_exit=1,
            diff_bytes=128,
            text="Done.",
        )
        == WRONG_FIX
    )


def test_semantic_terminal_state_detects_no_diff():
    assert (
        classify_semantic_terminal_state(
            terminal_reason="max_turns",
            verify_exit=1,
            hidden_exit=1,
            diff_bytes=0,
            text="I inspected the files but did not change anything.",
        )
        == NO_DIFF
    )


def test_semantic_terminal_state_detects_not_run():
    assert (
        classify_semantic_terminal_state(
            terminal_reason=None,
            verify_exit="not_run",
            hidden_exit="not_run",
            diff_bytes=0,
            text="",
        )
        == NOT_RUN
    )


def test_semantic_terminal_state_marks_green_completed_without_claim_as_unverified():
    assert (
        classify_semantic_terminal_state(
            terminal_reason="completed",
            verify_exit=0,
            hidden_exit=0,
            diff_bytes=128,
            text="Done.",
        )
        == DONE_UNVERIFIED
    )
