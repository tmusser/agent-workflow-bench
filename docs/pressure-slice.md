# Pressure Slice

This workflow compares the same task under deterministic synthetic context pressure.
It is a degradation check, not a new benchmark task and not a claim of broad model superiority.

## Run The Slice

Use the same pressure seed for the `medium` and `high` runs. `none` ignores the seed, but keeping it fixed makes the set easier to compare.

```bash
export PRESSURE_SEED=7
export TASK_SLUG=04-impossible-churn
ARM_SLUG=A-baseline \
RUN_ID=v04pilot_04-bugfix_pressure_A_none_r1 \
CLAUDE_MODEL=haiku \
CLAUDE_EFFORT=low \
CLAUDE_OUTPUT_FORMAT=json \
CLAUDE_PERMISSION_MODE=acceptEdits \
./tools/pilot_smoke.sh --pressure-level none --pressure-seed $PRESSURE_SEED --context-window-tokens 32000 auto-a-r1

ARM_SLUG=A-baseline \
RUN_ID=v04pilot_04-bugfix_pressure_A_medium_r1 \
CLAUDE_MODEL=haiku \
CLAUDE_EFFORT=low \
CLAUDE_OUTPUT_FORMAT=json \
CLAUDE_PERMISSION_MODE=acceptEdits \
./tools/pilot_smoke.sh --pressure-level medium --pressure-seed $PRESSURE_SEED --context-window-tokens 32000 auto-a-r1

ARM_SLUG=A-baseline \
RUN_ID=v04pilot_04-bugfix_pressure_A_high_r1 \
CLAUDE_MODEL=haiku \
CLAUDE_EFFORT=low \
CLAUDE_OUTPUT_FORMAT=json \
CLAUDE_PERMISSION_MODE=acceptEdits \
./tools/pilot_smoke.sh --pressure-level high --pressure-seed $PRESSURE_SEED --context-window-tokens 32000 auto-a-r1

ARM_SLUG=E-ai-engineering-skills \
RUN_ID=v04pilot_04-bugfix_pressure_E_none_r1 \
CLAUDE_MODEL=haiku \
CLAUDE_EFFORT=low \
CLAUDE_OUTPUT_FORMAT=json \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_PLUGIN_DIR="$PWD/local_plugins/ai-engineering-skills" \
./tools/pilot_smoke.sh --pressure-level none --pressure-seed $PRESSURE_SEED --context-window-tokens 32000 auto-a-r1

ARM_SLUG=E-ai-engineering-skills \
RUN_ID=v04pilot_04-bugfix_pressure_E_medium_r1 \
CLAUDE_MODEL=haiku \
CLAUDE_EFFORT=low \
CLAUDE_OUTPUT_FORMAT=json \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_PLUGIN_DIR="$PWD/local_plugins/ai-engineering-skills" \
./tools/pilot_smoke.sh --pressure-level medium --pressure-seed $PRESSURE_SEED --context-window-tokens 32000 auto-a-r1

ARM_SLUG=E-ai-engineering-skills \
RUN_ID=v04pilot_04-bugfix_pressure_E_high_r1 \
CLAUDE_MODEL=haiku \
CLAUDE_EFFORT=low \
CLAUDE_OUTPUT_FORMAT=json \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_PLUGIN_DIR="$PWD/local_plugins/ai-engineering-skills" \
./tools/pilot_smoke.sh --pressure-level high --pressure-seed $PRESSURE_SEED --context-window-tokens 32000 auto-a-r1
```

Manual `--pressure-target-pct` values are fractions of the configured context window and are capped at `0.95` to prevent accidental runaway prompt generation.

## Summarize

After the six runs finish, score the bundles and render the compact degradation table:

```bash
python -m benchmark_harness.scorecard \
  v04pilot_04-bugfix_pressure_A_none_r1-eval-bundle.tar.gz \
  v04pilot_04-bugfix_pressure_A_medium_r1-eval-bundle.tar.gz \
  v04pilot_04-bugfix_pressure_A_high_r1-eval-bundle.tar.gz \
  v04pilot_04-bugfix_pressure_E_none_r1-eval-bundle.tar.gz \
  v04pilot_04-bugfix_pressure_E_medium_r1-eval-bundle.tar.gz \
  v04pilot_04-bugfix_pressure_E_high_r1-eval-bundle.tar.gz \
  --json-out benchmark-data/summaries/pressure_slice_scorecard.json

python -m benchmark_harness.pressure_slice_summary \
  --scorecard-json benchmark-data/summaries/pressure_slice_scorecard.json \
  --task-slug 04-impossible-churn \
  --out benchmark-data/summaries/pressure_slice_degradation.md
```

The summary table shows:

- `task_slug`, `arm_slug`, and `pressure_level` for the run identity;
- `pressure_seed`, `pressure_tokens_estimated`, and `estimated_context_utilization` for the synthetic load;
- `max_context_utilization` when actual usage metadata exists;
- `verify_result` and `hidden_result` as `pass`, `fail`, or `n/a`;
- existing artifact/content indicators such as `initial_green`, `artifact_mechanism_active`, and `skill_runtime_proof_valid`;
- existing latency/runtime indicators such as `initial_first_functional_green_turn`, `initial_first_bench_ready_green_turn`, and `finalizer_total_cost_usd`.

`estimated_context_utilization` is synthetic-pressure-only: `pressure_tokens_estimated / context_window_tokens`. It does not represent the full rendered prompt or all model-visible state.

If `max_context_utilization` is `?`, the run did not expose actual usage data. That is expected for some local runs and should not break the table. When present, `max_context_utilization` is the best available actual input-token utilization for the configured context window.

## Safe Claims

Safe:

- "Under synthetic context pressure, A stayed green while E degraded on this task."
- "This run shows a measurable change in latency or artifact behavior as pressure increased."
- "The pressure slice is useful for comparing degradation on the same task and harness settings."

Unsafe:

- "This proves one model is broadly better than another."
- "The pressure slice establishes general coding ability."
- "A single pressure run is enough to rank model quality."

## Notes

Keep the language narrow: this workflow measures degradation under synthetic context pressure. It does not change task semantics and it does not justify broad superiority claims.
