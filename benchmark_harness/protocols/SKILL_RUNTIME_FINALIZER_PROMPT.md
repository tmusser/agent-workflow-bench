# E-arm Audit Finalizer

You are running the E-arm audit finalizer.

The task solution is already complete. Do not change functional code, tests,
fixtures, task data, or benchmark harness code.

Your only job is to make the run bench-ready by producing the required audit
artifacts.

Required steps:
1. Read `.benchmark/SKILL_RUNTIME_CONTEXT.md`.
2. Ensure `VERIFY.md` exists and accurately records the verification
   commands/results already used.
3. Create `SKILL_RUNTIME_PROOF.md` from `.benchmark/SKILL_RUNTIME_CONTEXT.md`.
4. Run:

   `python3.11 -m benchmark_harness.validate_skill_runtime_proof SKILL_RUNTIME_PROOF.md`

5. If the validator fails, fix only `SKILL_RUNTIME_PROOF.md` / `VERIFY.md`.
6. Before final response, confirm the validator passes.

Forbidden:
- Do not edit `src/`, `tests/`, `fixtures/`, task data, or benchmark harness
  code.
- Do not change the functional solution.
