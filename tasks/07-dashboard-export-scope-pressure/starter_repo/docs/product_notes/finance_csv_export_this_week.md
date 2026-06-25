# Finance CSV Export This Week

This week we want a CSV download for the existing `finance_weekly` report.

Scope:
- Keep the existing JSON behavior intact.
- Add only the CSV path for `finance_weekly`.
- Do not redesign the export architecture.
- Do not touch chart rendering.
- Do not add new dependencies unless truly necessary.

Desired CSV columns, in order:

1. `week_start`
2. `region`
3. `segment`
4. `gross_revenue_cents`
5. `refunds_cents`
6. `net_revenue_cents`

Sorting:
- `week_start` ascending
- `region` ascending
- `segment` ascending

Filtering:
- `--week-start` should apply to the CSV export the same way it already applies to the JSON export.
- For `week-start=2026-06-01` and `region=EMEA`, the fixture contains two matching rows and both should be returned.
- If no rows match, return header-only CSV.

This is a focused export request, not a framework redesign.
