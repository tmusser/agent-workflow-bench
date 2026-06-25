Benchmark arm: B — Strong no-skill workflow prompt.

No skill pack is available. Use careful ordinary engineering judgment.

Before editing:
- read TASK.md and docs/product_notes/finance_csv_export_this_week.md;
- identify the existing JSON behavior and CSV seam that must stay narrow;
- preserve the current no-result behavior;
- keep the implementation focused.

While editing:
- preserve existing JSON exports;
- add the smallest CSV export support that satisfies TASK.md;
- keep the change limited to the finance_weekly row-selection and export path;
- add focused tests for CSV formatting, filters, and empty results;
- avoid generic export frameworks, charting refactors, or broad data-model changes.

Before finishing:
- run VERIFY.sh;
- leave a concise implementation note in the repository explaining:
  - what changed;
  - how JSON and CSV behave now;
  - what verification you ran and the result;
  - any remaining risks or assumptions.

Do not use reusable skill workflows or prescribed skill artifact templates.
