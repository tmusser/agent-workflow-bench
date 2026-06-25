Benchmark arm: E — ai-engineering-skills.

Use the ai-engineering-skills plugin, not just wrapper prose.

For this scope-pressure export task, a likely route is:

mini-spec -> scope-freeze -> build-one -> test-mini -> verify-contract -> handoff

Before coding, create `SPEC.md` with the finance_weekly-only export contract, CSV
columns and order, no-match behavior, region-filter seam, and non-goals.

Use compact durable artifacts where helpful, such as `SPEC.md`, `VERIFY.md`,
`HANDOFF.md`, or `IMPLEMENTATION_NOTE.md`.

Keep the implementation focused. The goal is bounded, verified, resumable work,
not more ceremony.

Read `.benchmark/SKILL_RUNTIME_CONTEXT.md` before creating `SKILL_RUNTIME_PROOF.md`.
Copy the exact `Pinned commit SHA` from that file. If the context file is missing,
stop and report the blocker instead of fabricating proof.

Before finishing, create `VERIFY.md`, `HANDOFF.md`, and `SKILL_RUNTIME_PROOF.md`.

`VERIFY.md` must capture live verification evidence:
- `./VERIFY.sh` result
- hidden evaluator result if run
- any command that could not run and why

`HANDOFF.md` should stay compact and state:
- finance-weekly-only scope;
- the stale 2022 roadmap is not current scope;
- do not import the attic export spike;
- do not refactor charting;
- the implementation seam;
- no-match CSV behavior: header-only CSV;
- likely continuation: add region at the finance row-selection seam, not a global
  filtering framework.

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
- do not write `unavailable`, `unknown`, `TBD`, `TO_BE_FILLED`, or blank values.
- For `Pre-run availability check` use the exact context values and keep
  `Result` as a single success word such as `available` or `pass`.

Use the actual namespaced skills you invoked, such as:
`/ai-engineering-skills:mini-spec`,
`/ai-engineering-skills:scope-freeze`,
`/ai-engineering-skills:build-one`,
`/ai-engineering-skills:test-mini`,
`/ai-engineering-skills:verify-contract`,
and `/ai-engineering-skills:handoff`.

Run the proof validator before finishing if possible.
