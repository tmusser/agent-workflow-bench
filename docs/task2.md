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

## Current Pilot Result

Task 2 has a completed Haiku smoke pair on PR #12's branch using:

- `CLAUDE_MODEL=haiku`
- `CLAUDE_EFFORT=low`
- `CLAUDE_OUTPUT_FORMAT=json`
- `CLAUDE_PERMISSION_MODE=acceptEdits`
- run IDs `t2_haiku_A_pr12_r1` and `t2_haiku_E_pr12_r1`

Both arms solved the task in the initial, full-resume, and stripped-resume phases.
All six phases passed public verification and the hidden evaluator.

Both arms made localized fixes in `src/acquisition/metrics.py`:

- A baseline used `str.strip()`, `str.lower()`, `fillna("unknown")`, and `replace("", "unknown")`.
- E ai-engineering-skills used `fillna("")`, `str.strip()`, `str.lower()`, and `replace("", "unknown")`.

Both variants preserve the report shape and pass the hidden evaluator.

### PR-branch smoke metrics

| Arm | Phase | Public + hidden | Terminal reason | Turns | Cost USD | Wall seconds | Bash denials |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| A baseline | initial | pass | max_turns | 21 | 0.1215269 | 59.389 | 5 |
| A baseline | full resume | pass | max_turns | 21 | 0.1453726 | 92.985 | 6 |
| A baseline | stripped resume | pass | max_turns | 21 | 0.1557815 | 91.348 | 2 |
| E ai-engineering-skills | initial | pass | max_turns | 21 | 0.1220764 | 62.690 | 3 |
| E ai-engineering-skills | full resume | pass | completed | 20 | 0.1273156 | 89.169 | 3 |
| E ai-engineering-skills | stripped resume | pass | max_turns | 21 | 0.1130606 | 61.476 | 4 |

Aggregate over initial/full/stripped:

| Arm | Turns | Cost USD | Wall seconds | Bash denials | Completed phases |
| --- | ---: | ---: | ---: | ---: | ---: |
| A baseline | 63 | 0.4226810 | 243.722 | 13 | 0 / 3 |
| E ai-engineering-skills | 62 | 0.3624526 | 213.335 | 10 | 1 / 3 |

### Reading

Task 2 is still a small bridge task, not broad benchmark proof. It is more realistic than
Task 1 because the fix requires ordering several normalization steps, but it remains a
localized bugfix.

The useful finding is that both arms solved the functional task across all phases, while
E had slightly better aggregate run metrics in this single sample: one fewer total turn,
lower total cost, lower wall time, fewer Bash denials, and one completed phase where A had
none. This is suggestive only, not enough to claim general superiority.

Artifact evidence is mixed but useful. The E initial run produced `VERIFY.md` and
validator-compatible `SKILL_RUNTIME_PROOF.md`; full resume retained those artifacts and
completed cleanly. Stripped resume removed those artifacts but still passed, which means
Task 2 is not hard enough by itself to show a strong artifact dependency.

A baseline also solved the task but left extra generated local files such as `test_fix.py`
and cache directories in some phases. Those did not affect hidden correctness, but they are
useful audit-hygiene signal.

The proof artifact demonstrates pinned skill availability, agent-facing E wrapper
activation, and validator-compatible runtime evidence. It is not a private runtime trace
of every slash-command invocation.

Generated bundles contain local paths and should not be committed or published raw.
Publish summaries and scorecards instead.

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
