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
