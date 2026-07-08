Benchmark arm: E — ai-engineering-skills.

ai-engineering-skills is available.

Use the smallest workflow that fits the task. For this metric migration, a likely route is:

mini-spec -> scope-freeze -> build-one -> test-mini -> verify-contract -> handoff

Before coding, create `SPEC.md` with the v1/v2 metric definitions, denominator, numerator,
exclusions, and non-goals.

Use compact durable artifacts where helpful, such as `SPEC.md`, `VERIFY.md`, `HANDOFF.md`,
or `MIGRATION_NOTES.md`.

Create `SKILL_TRACE.jsonl` when using or skipping workflow skills. Keep it tiny: 2-5 JSONL rows is enough. Each line must be one JSON object with `event_type` and `skill_name`.
Add `turn_index` when a declared skill event naturally maps to a specific turn.

Allowed `event_type` values:
- `skill_available`
- `skill_considered`
- `skill_invoked`
- `skill_skipped`

This is agent-declared trace evidence, not runtime-hook proof. Do not let trace writing delay the first implementation edit or expand the migration ceremony.

Keep the implementation focused. The goal is bounded, verified, resumable work, not more ceremony.

Read `.benchmark/SKILL_RUNTIME_CONTEXT.md` before creating `SKILL_RUNTIME_PROOF.md`.
Copy the exact `Pinned commit SHA` from that file. If the context file is missing, stop and
report the blocker instead of fabricating proof.

Before finishing, create `VERIFY.md`, `HANDOFF.md`, and `SKILL_RUNTIME_PROOF.md`.

`VERIFY.md` must capture live verification evidence:
- `./VERIFY.sh` result
- hidden evaluator result if run
- any command that could not run and why

`HANDOFF.md` should stay compact and state what changed, what is safe to rely on, the
remaining risks, and the next safe continuation step.

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
- Invocation evidence level:
- Did the agent mention or invoke the skill? yes/no/unclear:
- Evidence:
- Notes:

## Post-run caveat
- Could a bad result be due to the skill not being loaded? yes/no/unclear:
- Reviewer notes:
```

Use the pinned skill repo information available in the run environment or local plugin
setup. List the actual namespaced skills you used, such as
`/ai-engineering-skills:mini-spec`, `/ai-engineering-skills:test-mini`,
`/ai-engineering-skills:verify-contract`, and `/ai-engineering-skills:handoff`.

Use real values, not prose:
- Use the values from `.benchmark/SKILL_RUNTIME_CONTEXT.md`.
- `Pinned commit SHA` must be the actual 40-character lowercase commit SHA from the
  pinned checkout, not a guessed or stale value.
- `Invocation evidence level` must be one of `availability_only`,
  `artifact_inferred`, `agent_declared`, or `runtime_hook`.
- Do not claim `runtime_hook` unless the evidence came from an actual runtime hook.
- Do not write `unavailable`, `unknown`, `TBD`, `TO_BE_FILLED`, or blank values.
- `Pre-run availability check`:
  - `Command run`: the exact local command you used to confirm the plugin checkout and
    skill visibility.
  - `Result`: use a single success word like `available` or `pass`.
  - `Evidence path`: point to the command output or log file.

Run the proof validator before finishing if possible.
