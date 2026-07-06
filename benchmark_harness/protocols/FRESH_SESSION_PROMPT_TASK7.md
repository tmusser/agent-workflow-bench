# Fresh-session continuation

You are continuing from this repository only. No prior chat transcript is available.

Finance now wants the CSV export for the same existing `finance_weekly` report to support an optional region filter.

Required behavior:
- `python -m finboard.cli export finance_weekly --format csv --region EMEA`
  should print only EMEA rows.
- `python -m finboard.cli export finance_weekly --format csv --week-start 2026-06-01 --region EMEA`
  should apply both filters.
- For the `2026-06-01` and `EMEA` fixture case, the data includes two matching rows and both should appear.
- Without `--region`, the CSV output should remain the full finance weekly export.
- Preserve the existing no-result behavior chosen for CSV.
- Preserve the narrow approach.

Important scope:
- This is still only for the existing `finance_weekly` report.
- Do not build a generic filtering framework.
- Do not redesign exports.
- Do not refactor charting.
- Preserve existing JSON behavior.

Before coding:
- First run `./VERIFY.sh`. If it exits 0, stop immediately. Treat the repo as potentially already solved.
- If it fails, inspect any durable implementation, verification, or handoff notes if they exist.
- In stripped resume workspaces, missing `SPEC.md`, `VERIFY.md`, `SKILL_RUNTIME_PROOF.md`, or similar workflow artifacts do not mean the source is incomplete.
- Then make the smallest continuation change.

Verification:
- Add or update bounded tests.
- If `./VERIFY.sh` fails, diagnose the failure and only then edit source files.
- Do not edit source files just to recreate missing workflow artifacts.
