# Task 7: Finance Weekly CSV Export

Task 7 checks whether an agent can add a narrow CSV export to the existing
`finance_weekly` report without widening the implementation or breaking the
current JSON behavior.

Internal description: Narrow dashboard export under scope pressure.

## What This Tests

- keeping the export seam narrow;
- preserving existing JSON exports;
- handling CSV ordering and no-match behavior deterministically;
- using fresh-session context to continue the work with a small, focused change.

## Starter Repo

The starter repo lives at `tasks/07-dashboard-export-scope-pressure/starter_repo`.

Public verification is table stakes only:

```bash
cd tasks/07-dashboard-export-scope-pressure/starter_repo
./VERIFY.sh
```

## Smoke Helper Examples

```bash
TASK_SLUG=07-dashboard-export-scope-pressure \
TASK_ID=07-dashboard-export \
ARM_SLUG=A-baseline \
RUN_ID=v07pilot_07-dashboard-export_A_r1 \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_MAX_TURNS=50 \
./tools/pilot_smoke.sh auto-a-r1
```

```bash
TASK_SLUG=07-dashboard-export-scope-pressure \
TASK_ID=07-dashboard-export \
ARM_SLUG=B-strong-no-skill \
RUN_ID=v07pilot_07-dashboard-export_B_r1 \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_MAX_TURNS=50 \
./tools/pilot_smoke.sh auto-a-r1
```

```bash
TASK_SLUG=07-dashboard-export-scope-pressure \
TASK_ID=07-dashboard-export \
ARM_SLUG=E-ai-engineering-skills \
RUN_ID=v07pilot_07-dashboard-export_E_r1 \
CLAUDE_PLUGIN_DIR="$PWD/local_plugins/ai-engineering-skills" \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_MAX_TURNS=60 \
./tools/pilot_smoke.sh auto-a-r1
```

For the E-arm local plugin checkout and runtime-proof flow, see
[skill-arm-setup.md](skill-arm-setup.md).

The fresh-session continuation prompt lives at
`benchmark_harness/protocols/FRESH_SESSION_PROMPT_TASK7.md`.

## Assessment Checks

The hidden evaluator checks the CLI output directly for:

- deterministic CSV header/order behavior;
- preserved JSON exports;
- optional region filtering in the fresh-session continuation;
- small, reviewable scope.

This is a scoped export task, not a generic export framework exercise.
