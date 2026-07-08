# Scorecard

`benchmark_harness.scorecard` summarizes one or more bundles into comparable rows.
It supports both completed eval bundles and initial-gate failure bundles.

## Supported Bundles

- Full eval bundles: `*-eval-bundle.tar.gz`
- Initial gate failure bundles: `*-initial-fail-bundle.tar.gz`

## Examples

Score one eval bundle:

```bash
python -m benchmark_harness.scorecard v04pilot_04-bugfix_A_r2-eval-bundle.tar.gz
```

Score a mixed set of eval and initial-fail bundles:

```bash
python -m benchmark_harness.scorecard \
  v04pilot_04-bugfix_A_r2-eval-bundle.tar.gz \
  v04pilot_04-bugfix_E_r4-eval-bundle.tar.gz \
  v05pilot_05-fake-data_A_r2-initial-fail-bundle.tar.gz \
  v05pilot_05-fake-data_E_r1-initial-fail-bundle.tar.gz
```

Write CSV and JSON outputs:

```bash
python -m benchmark_harness.scorecard \
  v04pilot_04-bugfix_A_r2-eval-bundle.tar.gz \
  v04pilot_04-bugfix_E_r4-eval-bundle.tar.gz \
  v05pilot_05-fake-data_A_r2-initial-fail-bundle.tar.gz \
  v05pilot_05-fake-data_E_r1-initial-fail-bundle.tar.gz \
  --out benchmark-data/scorecards/scorecard.csv \
  --json-out benchmark-data/scorecards/scorecard.json
```

## What It Measures

Scorecard rows are meant to compare:

- functional correctness
- assessment checks pass/fail
- workflow artifact presence
- fresh-session resume behavior
- artifact mechanism activation
- context-pressure configuration and estimated synthetic-pressure utilization

## Behavior Notes

- Full eval bundles may populate resume fields when resume artifacts are present.
- Initial-fail bundles do not have resume workspaces, so resume fields are reported as `not_run`.
- `artifact_mechanism_active` only becomes `true` when stripped artifacts were actually removed, not merely when workflow artifacts exist in the repo.
- `pressure_level`, `pressure_seed`, and `pressure_tokens_estimated` describe the synthetic background-context load injected by the runner.
- `estimated_context_utilization` is pressure-only: `pressure_tokens_estimated / context_window_tokens`. It does not represent the full rendered prompt or all model-visible state.
- `max_context_utilization` is only populated when actual usage metadata is available from the run.
- When `skill_runtime_recovery.json` is present, the scorecard uses it to distinguish `blocked: usage limit before task attempt`, `blocked: environment before task attempt`, and `failed: missing proof after task attempt` from plain functional failures.
- Task 5 yellow rows are useful negative results: they show the initial gate failed for the expected reasons, not that the scorecard itself is broken.

The scorecard is a reporting utility, not a new benchmark task.

Future scorecard columns may separate `skill_available`, `artifact_inferred`,
`agent_declared_trace`, and `runtime_hook_trace` so rows are less likely to be read
as if artifact evidence were invocation proof.

## Caution

A green row does not by itself prove broad skill superiority. It only says the run satisfied this bundle's checks and resume conditions.
Context-pressure comparisons are safe for narrow degradation claims on the same task and harness settings, not for broad claims about general model quality.
