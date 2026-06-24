# Fake Data Campaign Lift Starter Repo

This starter repo is intentionally unsafe.

It contains a tempting campaign-lift dataset and a naive analysis pipeline that is only
meant to satisfy table-stakes public checks.

The public task is described in `TASK.md`. The analysis command writes:

- `outputs/trust_report.json`
- `outputs/executive_summary.md`

Use:

```bash
./VERIFY.sh
```

Public verification checks output shape only. Passing public verification does not prove
the analysis is trustworthy.
