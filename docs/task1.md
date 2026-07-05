# Task 1: Support SLA Boundary Regression

Task 1 checks whether an agent can make a small, localized metric bugfix without
editing fixture data or changing the report shape.

The visible task fixes an inclusive/exclusive boundary bug in a support SLA report:
responses exactly at the SLA threshold are on time, not breached.

## What This Tests

- localized bugfix discipline;
- preserving existing report columns and grouping behavior;
- resisting fixture edits or fixture-specific hardcoding;
- basic hidden-contract behavior before the benchmark moves into resumability-heavy tasks;
- low-ceremony calibration for the `E-ai-engineering-skills` arm.

## Starter Repo

The starter repo lives at `tasks/01-support-sla-boundary/starter_repo`.

Public verification is table stakes only:

```bash
cd tasks/01-support-sla-boundary/starter_repo
./VERIFY.sh
```

The starter state is intentionally failing.

## Current Pilot Result

Task 1 has a completed Haiku smoke pair on merged `main` using:

- `CLAUDE_MODEL=haiku`
- `CLAUDE_EFFORT=low`
- `CLAUDE_OUTPUT_FORMAT=json`
- `CLAUDE_PERMISSION_MODE=acceptEdits`
- run IDs `t1_haiku_A_main_r1` and `t1_haiku_E_main_r1`

Both arms solved the task in the initial, full-resume, and stripped-resume phases.
All six phases passed public verification and the hidden evaluator.

Both arms made the same intended localized fix:

```diff
-    # BUG: exact-boundary responses are allowed, but this treats them as breaches.
-    result["sla_breached"] = result["response_hours"] >= result["sla_hours"]
+    result["sla_breached"] = result["response_hours"] > result["sla_hours"]
```

### Main-branch smoke metrics

| Arm | Phase | Public + hidden | Terminal reason | Turns | Cost USD | Wall seconds | Bash denials |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| A baseline | initial | pass | completed | 19 | 0.1144506 | 54.279 | 5 |
| A baseline | full resume | pass | completed | 27 | 0.1439570 | 85.728 | 3 |
| A baseline | stripped resume | pass | max_turns | 21 | 0.1315860 | 80.909 | 3 |
| E ai-engineering-skills | initial | pass | completed | 16 | 0.1018728 | 50.511 | 3 |
| E ai-engineering-skills | full resume | pass | completed | 26 | 0.1413688 | 91.967 | 3 |
| E ai-engineering-skills | stripped resume | pass | completed | 29 | 0.1607417 | 110.322 | 5 |

Aggregate over initial/full/stripped:

| Arm | Turns | Cost USD | Wall seconds | Bash denials |
| --- | ---: | ---: | ---: | ---: |
| A baseline | 67 | 0.3899936 | 220.916 | 11 |
| E ai-engineering-skills | 71 | 0.4039833 | 252.800 | 11 |

### Reading

Task 1 is an instrumentation and ceremony-calibration smoke, not evidence of broad
skill superiority.

The useful finding is that the original generic E wrapper overfit ceremony to a tiny
bug: the 20-turn diagnostic produced no diff, and a 40-turn diagnostic fixed the code
but failed the strict `SKILL_RUNTIME_PROOF.md` shape. After the generic E wrapper was
lightened and given an explicit proof template, the normal 20-turn E run became
resume-ready: it fixed the bug, produced `VERIFY.md`, produced validator-compatible
`SKILL_RUNTIME_PROOF.md`, and completed both resume phases.

On this task, the E arm is viable and artifact-producing but not clearly more efficient
in aggregate. The full-vs-stripped E comparison is mildly favorable to durable artifacts
(`26` turns / `$0.1413688` full versus `29` turns / `$0.1607417` stripped), but this is a
single easy task and should be treated as suggestive only.

The proof artifact demonstrates pinned skill availability, agent-facing E wrapper
activation, and validator-compatible runtime evidence. It is not a private runtime trace
of every slash-command invocation.

Generated bundles contain local paths and should not be committed or published raw.
Publish summaries and scorecards instead.

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
