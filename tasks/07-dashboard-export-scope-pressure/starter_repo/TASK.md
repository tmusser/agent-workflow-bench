# Task: Finance weekly CSV export

Add a CSV export for the existing `finance_weekly` dashboard report.

Current behavior:
- Existing JSON exports must keep working.
- `python -m finboard.cli export finance_weekly --format json` works.
- `python -m finboard.cli export finance_weekly --format json --week-start YYYY-MM-DD` works.
- When a JSON filter matches no finance rows, the existing behavior is an empty JSON list.

Required new behavior:
- `python -m finboard.cli export finance_weekly --format csv` should print CSV to stdout.
- `python -m finboard.cli export finance_weekly --format csv --week-start YYYY-MM-DD` should apply the same existing week filter.
- The `week-start=2026-06-01` / `region=EMEA` fixture case should return both matching rows.
- If the filter matches no rows, preserve the existing no-result semantics in CSV form.

CSV columns must be, in this order:

week_start,region,segment,gross_revenue_cents,refunds_cents,net_revenue_cents

Rows should be sorted by:
1. week_start ascending
2. region ascending
3. segment ascending

Important scope:
- Use `docs/product_notes/finance_csv_export_this_week.md` as the current product source of truth.
- Keep this narrow: just the existing `finance_weekly` report.
- Do not build a generic export framework.
- Do not refactor charting.
- Do not add new dependencies unless truly necessary.
- Preserve existing public behavior.

Verification:
- Update or add bounded tests for the new CSV behavior.
- Run `./VERIFY.sh`.
