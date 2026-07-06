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
3. Immediately implement the smallest functional diff.
4. Run verification.
5. Then create compact `VERIFY.md`, `HANDOFF.md`, and `SKILL_RUNTIME_PROOF.md`.

Do not stop after planning. A `SPEC.md` without code changes is a failed run.
If context is noisy or the turn budget feels tight, collapse ceremony toward
execution: one short spec, edit, test, verify, proof.

Use namespaced skills where helpful, but do not spend the run reciting the full
chain. Prefer execution-first use of:

- `/ai-engineering-skills:mini-spec` for the compact contract only;
- `/ai-engineering-skills:build-one` for the smallest implementation seam;
- `/ai-engineering-skills:test-mini` for targeted public/hidden-facing checks;
- `/ai-engineering-skills:verify-contract` for final evidence;
- `/ai-engineering-skills:handoff` only after the fix is verified.

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
- Add region filtering at the finance row-selection seam, not as a global
  filtering framework.

Read `.benchmark/SKILL_RUNTIME_CONTEXT.md` before creating
`SKILL_RUNTIME_PROOF.md`. Copy the exact `Pinned commit SHA` from that file. If
the context file is missing, stop and report the blocker instead of fabricating
proof.

`VERIFY.md` must capture live verification evidence:

- `./VERIFY.sh` result;
- hidden evaluator result if run;
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

The proof must include these sections and non-placeholder fields:

```md
# Skill Runtime Proof

## Run
- Run ID:
- Arm:
- Task:
- Repeat:

## Skill source
- Repo URL:
- Pinned commit SHA:
- Local path:
- Install command:
- Install stdout/stderr path:

## Activation
- Agent CLI:
- Activation mechanism:
- Prompt wrapper path:
- Agent-visible skill files:
- Environment variables relevant to skill loading:

## Pre-run availability check
- Command run:
- Result:
- Evidence path:

## During-run evidence
- Did the agent mention or invoke the skill? yes/no/unclear:
- Evidence:
- Notes:

## Post-run caveat
- Could a bad result be due to the skill not being loaded? yes/no/unclear:
- Reviewer notes:
```

Use real values, not prose:

- use the values from `.benchmark/SKILL_RUNTIME_CONTEXT.md`;
- `Pinned commit SHA` must be the actual 40-character lowercase SHA from the
  pinned checkout, not a guessed or stale value;
- do not write `unavailable`, `unknown`, `TBD`, `TO_BE_FILLED`, or blank values;
- for `Pre-run availability check`, use the exact context values and keep
  `Result` as a single success word such as `available` or `pass`.

Run the proof validator before finishing if possible.
