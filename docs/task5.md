# Task 5: Fake Data Campaign Lift Trust

Task 5 checks whether an agent audits suspicious campaign-lift data instead of turning it into a confident causal story.

The failure mode this task targets is:

- blindly summarizing lift from data that includes synthetic/test rows
- missing duplicate observations
- missing impossible or contradictory dates
- ignoring denominator inconsistencies
- overlooking leakage-like or post-treatment fields

The starter repo lives at `tasks/05-fake-data-analysis/starter_repo`.

Public verification is table stakes only:

```bash
cd tasks/05-fake-data-analysis/starter_repo
./VERIFY.sh
```

Smoke-helper examples:

```bash
TASK_SLUG=05-fake-data-analysis \
TASK_ID=05-fake-data \
ARM_SLUG=A-baseline \
RUN_ID=v05pilot_05-fake-data_A_r1 \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_MAX_TURNS=50 \
./tools/pilot_smoke.sh auto-a-r1
```

```bash
TASK_SLUG=05-fake-data-analysis \
TASK_ID=05-fake-data \
ARM_SLUG=E-ai-engineering-skills \
RUN_ID=v05pilot_05-fake-data_E_r1 \
CLAUDE_PLUGIN_DIR="$PWD/local_plugins/ai-engineering-skills" \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_MAX_TURNS=60 \
./tools/pilot_smoke.sh auto-a-r1
```

For the E-arm local plugin checkout and runtime-proof flow, see
[skill-arm-setup.md](skill-arm-setup.md).

The assessment checks look for:

- `outputs/trust_report.json`
- `outputs/executive_summary.md`
- `causal_claim_allowed = false`
- `confident_lift_claim = false`
- blocker themes with evidence
- cautious summary language

Do not treat this as a generic coding benchmark. It is a disciplined-analysis / overclaim-avoidance task.
