# Ceremony Budget — Task 7 E

Use process as a scarce budget, not a ritual.

## Budget contract

- Planning budget: create at most one compact SPEC.md before implementation.
- Build budget: start code changes before spending time on secondary artifacts.
- Verification budget: run ./VERIFY.sh after the smallest plausible passing diff.
- Diagnostic budget: after a verification failure, inspect the first traceback and the actual import/call path used by the failing command before editing unrelated files.
- Proof reserve: reserve final turns for VERIFY.md, HANDOFF.md, and SKILL_RUNTIME_PROOF.md, even if verification still fails.

## Throttle rules

- If context is noisy, reduce artifact size before reducing implementation effort.
- If the task is small and the failure is concrete, collapse toward edit -> verify -> diagnose.
- Do not stop after SPEC.md.
- Do not treat a tiny code edit as sufficient if a known required public check is still failing.
- Do not encode hidden evaluator answers. Use only task text, public tests, tracebacks, and visible code paths.

## Required budget ledger

Before finishing, include a compact budget ledger in VERIFY.md or HANDOFF.md:

- Planning spent:
- Build spent:
- Verification spent:
- Diagnostic spent:
- Proof reserve used:
- First failing traceback inspected:
- Actual call path checked:
