# Task 1: Support SLA Boundary Regression

Task 1 checks whether an agent can make a small, localized metric bugfix without
editing fixture data or changing the report shape.

The visible task fixes an inclusive/exclusive boundary bug in a support SLA report:
responses exactly at the SLA threshold are on time, not breached.

## What This Tests

- localized bugfix discipline;
- preserving existing report columns and grouping behavior;
- resisting fixture edits or fixture-specific hardcoding;
- basic hidden-contract behavior before the benchmark moves into resumability-heavy tasks.

## Starter Repo

The starter repo lives at `tasks/01-support-sla-boundary/starter_repo`.

Public verification is table stakes only:

```bash
cd tasks/01-support-sla-boundary/starter_repo
./VERIFY.sh
```

The starter state is intentionally failing.

## Smoke Helper Examples

```bash
TASK_SLUG=01-support-sla-boundary \
TASK_ID=01-sla-boundary \
ARM_SLUG=A-baseline \
RUN_ID=v01pilot_01-sla-boundary_A_r1 \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_MAX_TURNS=30 \
./tools/pilot_smoke.sh auto-a-r1
```

```bash
TASK_SLUG=01-support-sla-boundary \
TASK_ID=01-sla-boundary \
ARM_SLUG=E-ai-engineering-skills \
RUN_ID=v01pilot_01-sla-boundary_E_r1 \
CLAUDE_PLUGIN_DIR="$PWD/local_plugins/ai-engineering-skills" \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_MAX_TURNS=40 \
./tools/pilot_smoke.sh auto-a-r1
```

For the E-arm local plugin checkout and runtime-proof flow, see
[skill-arm-setup.md](skill-arm-setup.md).

## Assessment Checks

The hidden evaluator checks for:

- unchanged `fixtures/tickets.csv`;
- exact-boundary urgent and standard tickets classified as on time;
- over-boundary urgent and standard tickets classified as breached;
- preserved report columns and expected grouped counts;
- no obvious fixture-specific hardcoding.

This is the benchmark's low-ceremony warmup task. It should not need a fresh-session
continuation to be informative.
