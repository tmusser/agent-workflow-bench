# Task 6 — Activation Metric v2 Migration

Task 6 checks whether an agent can migrate a monthly activation metric without breaking the earlier definition, losing the public audit trail, or confusing a fresh-session continuation.

## What This Tests

- metric definition discipline;
- denominator and numerator preservation across a version change;
- v1/v2 migration compatibility;
- public-pass / hidden-fail behavior;
- fresh-session continuation and resumability.

## What This Does Not Prove

- not broad skill superiority;
- not that workflow skills guarantee correctness;
- not that artifacts should be scored as functional correctness.

## Starter Repo Status

- The starter repo is intentionally incomplete.
- Its local public verification is expected to fail until a benchmark agent implements v2.
- Repo-level harness tests should still pass.

## Arms

### A — Generic baseline

- No skill pack.
- Normal coding-agent behavior.
- Receives neutral runner constraints plus the public `TASK.md`.

### B — Strong no-skill driver

- No skill pack.
- Asks for careful engineering, edge cases, tests, verification, and a concise implementation note.
- Must not use `ai-engineering-skills` terminology or templates.

### E — Skill-routed workflow

- `ai-engineering-skills` is available.
- A likely route is:
  `mini-spec -> scope-freeze -> build-one -> test-mini -> verify-contract -> handoff`
- Compact durable artifacts are allowed where they are useful.

## Common Runner Wrapper

```text
You are running inside a local coding-agent benchmark.

Runner constraints:
- Use only local files and local commands.
- Do not use external APIs or network services.
- Read TASK.md before editing.
- Run VERIFY.sh before finishing if the repository provides it.
- Do not ask follow-up questions unless the task is impossible without an answer.
- If blocked, state the blocker clearly and stop.
- Keep working until the task is complete, blocked, or the runner stops you.
```

The common wrapper must not tell every arm to create handoff artifacts.
The common wrapper must not tell every arm to preserve fresh-session state.
Those behaviors are part of what B and E are meant to test.

## B Strong No-Skill Wrapper

```text
Benchmark arm: B — Strong no-skill driver prompt.

No skill pack is available. Use careful ordinary engineering judgment.

Before editing:
- read TASK.md and the product brief;
- identify the existing behavior that must remain backward-compatible;
- identify likely metric edge cases from the brief and data model;
- keep the implementation focused.

While editing:
- preserve the existing v1 API and behavior;
- implement the smallest v2 support that satisfies the product brief;
- add meaningful tests for behavior you change;
- avoid broad rewrites, dashboards, databases, services, schedulers, or analytics platforms.

Before finishing:
- run VERIFY.sh;
- leave a concise implementation note in the repository explaining:
  - what changed;
  - how v1 and v2 are defined;
  - what verification you ran and the result;
  - any remaining risks or assumptions.

Do not use reusable skill workflows or prescribed skill artifact templates.
```

## E Wrapper

```text
Benchmark arm: E — ai-engineering-skills.

ai-engineering-skills is available.

Use the smallest workflow that fits the task. For this metric migration, a likely route is:

mini-spec -> scope-freeze -> build-one -> test-mini -> verify-contract -> handoff

Use compact durable artifacts where helpful, such as SPEC.md, VERIFY.md, HANDOFF.md, or MIGRATION_NOTES.md.

Keep the implementation focused. The goal is bounded, verified, resumable work, not more ceremony.
```

## Fresh-Session Resume Request

```text
A product analyst now asks for a local comparison report showing v1 and v2 activation rates side by side for January and February.

Use the existing migration state. Keep the change small.

Expected output:
- `outputs/activation_v1_v2_comparison.csv`
- one row per month;
- columns:
  - `month`
  - `v1_eligible_users`
  - `v1_activated_users`
  - `v1_activation_rate`
  - `v2_eligible_users`
  - `v2_activated_users`
  - `v2_activation_rate`

Preserve the existing v1 and v2 definitions.
Run the repo verification before finishing.
```

## Resume Conditions

- The full workspace includes code, tests, fixtures, outputs, and any agent-created workflow artifacts.
- The artifact-stripped workspace removes workflow artifacts only.
- The required public docs remain `README.md`, `TASK.md`, and `docs/product_activation_v2.md`.
- The same resume prompt is used in both conditions.
- The agent does not know which condition it is in.

## Planned Score Fields

- `hidden_contract_pass`
- `v1_preserved`
- `v2_correct`
- `zero_denominator_handled`
- `workflow_audit_score`
- `resume_score_full`
- `resume_score_stripped`
- `artifact_resume_delta`
- `resume_redefined_metric`
- `resume_preserved_v1_v2_definitions`

## Claim Boundary

- Functional hidden pass is separate from workflow/audit score.
- A red hidden / strong audit result is still informative.
- A B arm matching E is allowed and would narrow the claim.
