# Task 3: Product Refund Grain Regression

Task 3 checks whether an agent can fix a small aggregation-grain bug without
rewriting the report path or shortcutting the expected fixture rows.

The visible task fixes a product refund-rate report that counts refund events instead
of distinct refunded orders. One order can have multiple refund events, but refund
rate is order-based.

## What This Tests

- aggregation-grain discipline;
- preserving existing report columns and product grouping behavior;
- distinguishing event counts from entity counts;
- resisting fixture edits, clamps, or fixture-specific hardcoding;
- a middle rung below Task 4's temporal join and fresh-session resumability pressure.

## Starter Repo

The starter repo lives at `tasks/03-refund-grain/starter_repo`.

Public verification is table stakes only:

```bash
cd tasks/03-refund-grain/starter_repo
./VERIFY.sh
```

The starter state is intentionally failing.

## Current Haiku Smoke Result

Task 3 was piloted on PR #12 with `CLAUDE_MODEL=haiku`,
`CLAUDE_EFFORT=low`, `CLAUDE_OUTPUT_FORMAT=json`, and
`CLAUDE_PERMISSION_MODE=acceptEdits`.

Bundles inspected:

- `t3_haiku_A_pr12_r1-eval-bundle.tar.gz`
- `t3_haiku_E_pr12_r1-eval-bundle.tar.gz`

Both A and E solved the task across initial, full-resume, and stripped-resume
phases. All six phases passed public verification and the hidden evaluator.

Both arms made the intended localized fix in `src/commerce/metrics.py`, changing
the refund-rate numerator from refund-event rows to unique refunded `order_id`
values:

```diff
- refunds_with_product.groupby("product", sort=True)["refund_id"].count()
+ refunds_with_product.groupby("product", sort=True)["order_id"].nunique()
```

| Arm | Phase | Public + hidden | Terminal reason | Turns | Cost USD | Wall seconds | Bash denials |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| A baseline | initial | pass | completed | 19 | 0.1014737 | 57.992 | 4 |
| A baseline | full resume | pass | completed | 25 | 0.1475606 | 104.811 | 4 |
| A baseline | stripped resume | pass | max_turns | 21 | 0.1642659 | 90.325 | 6 |
| E ai-engineering-skills | initial | pass | max_turns | 21 | 0.1229446 | 73.806 | 4 |
| E ai-engineering-skills | full resume | pass | max_turns | 21 | 0.1208485 | 56.998 | 3 |
| E ai-engineering-skills | stripped resume | pass | max_turns | 21 | 0.1431343 | 81.557 | 4 |

Aggregate over initial/full/stripped:

| Arm | Turns | Cost USD | Wall seconds | Bash denials | Completed phases |
| --- | ---: | ---: | ---: | ---: | ---: |
| A baseline | 65 | 0.4133002 | 253.128 | 14 | 2 / 3 |
| E ai-engineering-skills | 63 | 0.3869274 | 212.361 | 11 | 0 / 3 |

Reading:

- Task 3 adds another green smoke/bridge result and validates the refund-grain
  task design.
- E was cheaper/faster overall and had fewer Bash denials in this sample.
- A had cleaner terminal completions in the initial and full-resume phases.
- E produced expected proof artifacts in initial/full contexts, which is useful
  audit evidence but not enough to claim broad superiority.
- `max_turns` should not be read as functional failure when public and hidden
  verification pass. Functional result and terminal result should be interpreted
  separately.

## Smoke Helper Examples

```bash
TASK_SLUG=03-refund-grain \
TASK_ID=03-refund-grain \
ARM_SLUG=A-baseline \
RUN_ID=v03pilot_03-refund-grain_A_r1 \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_MAX_TURNS=35 \
./tools/pilot_smoke.sh auto-a-r1
```

```bash
TASK_SLUG=03-refund-grain \
TASK_ID=03-refund-grain \
ARM_SLUG=E-ai-engineering-skills \
RUN_ID=v03pilot_03-refund-grain_E_r1 \
CLAUDE_PLUGIN_DIR="$PWD/local_plugins/ai-engineering-skills" \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_MAX_TURNS=45 \
./tools/pilot_smoke.sh auto-a-r1
```

For the E-arm local plugin checkout and runtime-proof flow, see
[skill-arm-setup.md](skill-arm-setup.md).

## Assessment Checks

The hidden evaluator checks for:

- unchanged `fixtures/orders.csv` and `fixtures/refund_events.csv`;
- duplicate refund events counted once per refunded order;
- preserved product rows, report columns, and expected grouped counts;
- no clamping of refund rates as a substitute for fixing the grain;
- no obvious fixture-specific hardcoding.

This is the bridge from simple input bugs to Task 4's more complex metric-grain and
resume behavior.
