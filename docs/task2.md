# Task 2: Campaign Channel Normalization

Task 2 checks whether an agent can fix a small input-normalization bug without
changing fixture data, report shape, or the surrounding reporting path.

The visible task fixes a campaign-channel report that splits equivalent labels
such as `Email`, ` email `, and blank values into separate or missing rows.

## What This Tests

- input normalization discipline;
- preserving existing report columns and grouping behavior;
- handling blank and missing labels deterministically;
- resisting fixture edits or fixture-specific hardcoding;
- a slightly larger fix surface than Task 1, without Task 4-style resumability pressure.

## Starter Repo

The starter repo lives at `tasks/02-channel-normalization/starter_repo`.

Public verification is table stakes only:

```bash
cd tasks/02-channel-normalization/starter_repo
./VERIFY.sh
```

The starter state is intentionally failing.

## Smoke Helper Examples

```bash
TASK_SLUG=02-channel-normalization \
TASK_ID=02-channel-normalization \
ARM_SLUG=A-baseline \
RUN_ID=v02pilot_02-channel-normalization_A_r1 \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_MAX_TURNS=30 \
./tools/pilot_smoke.sh auto-a-r1
```

```bash
TASK_SLUG=02-channel-normalization \
TASK_ID=02-channel-normalization \
ARM_SLUG=E-ai-engineering-skills \
RUN_ID=v02pilot_02-channel-normalization_E_r1 \
CLAUDE_PLUGIN_DIR="$PWD/local_plugins/ai-engineering-skills" \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_MAX_TURNS=40 \
./tools/pilot_smoke.sh auto-a-r1
```

For the E-arm local plugin checkout and runtime-proof flow, see
[skill-arm-setup.md](skill-arm-setup.md).

## Assessment Checks

The hidden evaluator checks for:

- unchanged `fixtures/leads.csv`;
- trimmed, lowercased channel labels;
- blank and missing channel labels mapped to `unknown`;
- preserved report columns and expected grouped counts;
- no obvious fixture-specific hardcoding.

This is a bridge task: more realistic than Task 1's single boundary comparison, but
still intentionally smaller than Task 4.
