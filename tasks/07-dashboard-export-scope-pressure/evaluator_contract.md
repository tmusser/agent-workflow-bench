# Task 7 Assessment Contract

This file is for benchmark maintainers only. It is not part of the agent-visible starter repo.

## Initial functional expectations

- Existing JSON exports remain available.
- `finance_weekly` supports the current week filter for JSON.
- Missing finance rows in JSON return an empty list.
- `ops_daily` continues to export in JSON.
- The fixture has two `EMEA` rows for `week-start=2026-06-01`; combined week+region filtering should return both rows.

## Scope expectations

- Add CSV only for the existing `finance_weekly` report.
- Keep the change narrow.
- Do not introduce a generic export framework.
- Do not refactor charting or unrelated registry code.

## Artifact expectations

- Preserve the current JSON behavior.
- Use the current product notes as the source of truth.
- Keep workflow artifacts out of the agent-visible scope when stripping later resume workspaces.

## Resume expectations

- Future resume logic should evaluate whether the agent preserved the narrow seam.
- Later hidden evaluation can inspect CSV shape, sort order, filter behavior, and no-match semantics.
