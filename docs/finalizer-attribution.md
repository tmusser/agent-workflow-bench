# Finalizer Attribution

E finalizer runs are measured as a separate audit partition. The main E run
measures functional solving; the finalizer measures the marginal cost of
producing and validating `SKILL_RUNTIME_PROOF.md`. We report finalizer turns,
wall time, and cost separately so bench-ready success does not hide the audit
tax.

The finalizer is artifact-only. If it changes functional files, the finalizer
is marked invalid and the run should not be treated as bench-ready via
finalizer.
