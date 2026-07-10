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

Current rows also surface normalized turn-trace metadata when
`agent_turn_trace_summary.json` is present:

- `initial_turn_trace_present`
- `initial_turn_trace_fidelity`
- `initial_turns_observed`
- `initial_file_changing_tool_uses_observed`
- `initial_checkpoints_observed`
- `initial_first_functional_green_turn`
- `initial_first_bench_ready_green_turn`
- `initial_skill_trace_evidence_level`

Equivalent `full_...` and `stripped_...` fields are emitted for the resume phases.

## Caution

A green row does not by itself prove broad skill superiority. It only says the run satisfied this bundle's checks and resume conditions.
Context-pressure comparisons are safe for narrow degradation claims on the same task and harness settings, not for broad claims about general model quality.

## Codex provider-item fields

When `agent_turn_trace_summary.json` contains a Codex provider-item timeline, the
scorecard surfaces item counts and milestones for each phase. These fields distinguish
command and file-change activity inside a single Codex provider turn. They are workflow
sequence metrics, not functional first-green claims.

## Codex first-green item fields

When JSONL checkpoint observation is enabled, phase-prefixed scorecard columns include
`first_functional_green_item`, `first_bench_ready_green_item`, both post-green item tails,
`functional_to_bench_ready_items`, and checkpoint coverage. Only interpret an exact first
green item when the corresponding `checkpoint_coverage_complete` field is true.

## Provider observability fields

v0.2.0 phase-prefixed rows expose the shared Claude/Codex snapshot contract:

- `checkpoint_coverage_complete`
- `stable_snapshot_coverage_complete`
- `checkpoint_evaluation_deferred`
- `checkpoint_boundary_resolution`
- `native_observation_unit`
- `workspace_states_observed` / `workspace_states_skipped`
- `checkpoint_snapshot_pause_seconds`
- `checkpoint_evaluator_seconds`

Use provider-native first-green fields only when coverage is complete. Claude turns and
Codex provider items are different units; compare outcomes, wall time, token use, and
normalized tail fractions rather than raw unit counts.
