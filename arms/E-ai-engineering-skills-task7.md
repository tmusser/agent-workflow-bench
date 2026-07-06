Benchmark arm: E — ai-engineering-skills.

Use the ai-engineering-skills plugin, not just wrapper prose.

This scope-pressure export task is intentionally small enough that excess
ceremony can become the failure mode. Use the lightest workflow that protects
the contract and spend the run on implementation plus verification.

Pressure-aware route:

1. Read the task and relevant code/tests.
2. Create a compact `SPEC.md` before coding, but keep it execution-sized:
   - finance_weekly-only CSV export contract;
   - required CSV columns and order;
   - sorting and no-match behavior;
   - week-start and region filter seams;
   - non-goals.
3. Immediately implement the smallest passing diff.
4. Run verification.
5. Then create compact `VERIFY.md`, `HANDOFF.md`, and `SKILL_RUNTIME_PROOF.md`.

Do not stop after planning. A `SPEC.md` without code changes is a failed run.
A tiny code edit that leaves a known required public check failing is also not
enough; continue through the known failing seam while turns remain. If context
is noisy or the turn budget feels tight, collapse ceremony toward execution:
one short spec, edit, test, verify, proof.

Use namespaced skills where helpful, but do not spend the run reciting the full
chain. Prefer execution-first use of:

- `/ai-engineering-skills:mini-spec` for the compact contract only;
- `/ai-engineering-skills:build-one` for the smallest implementation seam;
- `/ai-engineering-skills:test-mini` for targeted checks;
- `/ai-engineering-skills:verify-contract` for final evidence;
- `/ai-engineering-skills:handoff` only after the fix is verified or after a
  failed implementation attempt needs a continuation note.

Avoid using the full `mini-spec -> scope-freeze -> build-one -> test-mini ->
verify-contract -> handoff` chain if it would delay the first implementation
edit. The benchmark rewards bounded, verified, resumable work, not artifact
volume.

Implementation focus:

- Keep the implementation finance-weekly-only.
- Do not import the attic export spike.
- Do not refactor charting.
- Do not build a generic export framework.
- Preserve existing JSON behavior.
- Implement CSV at the finance row-selection/rendering seam.
- Preserve no-match CSV behavior as header-only CSV.
- Add `--region` support for `finance_weekly` and compose it with `--week-start`.
- Add region filtering at the finance row-selection seam, not as a global
  filtering framework.
- Do not assume a CLI-only change is sufficient. The likely passing seam spans
  argument parsing plus finance row selection/rendering.

Known required check:

```bash
python -m finboard.cli export finance_weekly --format csv --week-start 2026-06-01 --region EMEA
```

This command must parse successfully, return exit code 0, and output only the
matching EMEA rows for that week.

Read `.benchmark/SKILL_RUNTIME_CONTEXT.md` before creating
`SKILL_RUNTIME_PROOF.md`. Copy the exact `Pinned commit SHA` from that file. If
the context file is missing, stop and report the blocker instead of fabricating
proof.

Create `SKILL_RUNTIME_PROOF.md` even if verification still fails. A failed
implementation with a valid runtime proof is acceptable evidence for a failed E
run; a missing runtime proof is a wrapper failure and should be avoided.

`VERIFY.md` must capture live verification evidence:

- `./VERIFY.sh` result;
- any command that could not run and why.

`HANDOFF.md` should stay compact and state:

- finance-weekly-only scope;
- the stale 2022 roadmap is not current scope;
- do not import the attic export spike;
- do not refactor charting;
- the implementation seam;
- no-match CSV behavior: header-only CSV;
- likely continuation: add related finance filters at the finance row-selection
  seam, not through a global filtering framework.

`SKILL_RUNTIME_PROOF.md` must use the strict runtime-proof structure expected by:

```bash
python -m benchmark_harness.validate_skill_runtime_proof SKILL_RUNTIME_PROOF.md
```

Fill every field with concrete values. Do not leave placeholder values such as
`TO_BE_FILLED`, `TBD`, `unknown`, or blank fields.

Use real values, not prose:

- use the values from `.benchmark/SKILL_RUNTIME_CONTEXT.md`;
- `Pinned commit SHA` must be the actual 40-character lowercase SHA from the
  pinned checkout, not a guessed or stale value;
- do not write `unavailable`, `unknown`, `TBD`, `TO_BE_FILLED`, or blank values;
- for `Pre-run availability check`, use the exact context values and keep
  `Result` as a single success word such as `available` or `pass`.

Run the proof validator before finishing if possible.
