# Solution Latency

Semantic terminal state answers whether the final workspace was correct despite a
raw terminal shape such as `max_turns`. Solution latency asks a sharper question:

> On which turn did the run first become public + hidden green?

That requires per-turn evidence. Existing bundles usually contain only final
workspace state and final verification results, so the scorecard must not invent a
first-green turn from final logs alone.

## Scorecard Fields

For each phase, the scorecard includes:

- `<phase>_actual_turns`
- `<phase>_first_green_turn`
- `<phase>_turns_after_first_green`
- `<phase>_permission_denials_after_first_green`
- `<phase>_solution_latency_observable`
- `<phase>_solution_latency_source`
- `<phase>_solution_latency_note`

Phases use these prefixes:

- `initial`
- `full_resume`
- `stripped_resume`

## Current Bundle Behavior

For current bundles without per-turn traces:

- `actual_turns` can be read from `run_metrics.json` when present.
- `first_green_turn` remains empty.
- `turns_after_first_green` remains empty.
- `solution_latency_observable` is `false`.
- `solution_latency_note` is `not_observable`.

This is intentional. It preserves the difference between:

- **known**: the final workspace is green;
- **unknown**: the exact turn where it first became green.

## Future Bundle Inputs

The scorecard can compute first-green turn when a run directory includes one of
these optional files.

### `solution_latency.json`

```json
{
  "actual_turns": 21,
  "first_green_turn": 7,
  "turns_after_first_green": 14,
  "permission_denials_after_first_green": 3,
  "note": "computed_by_harness"
}
```

Only `first_green_turn` is required. When `actual_turns` is present in
`run_metrics.json`, `turns_after_first_green` can be derived.

### `turn_events.jsonl` or `solution_timeline.jsonl`

Each line is a JSON object. The first event with public + hidden green status is
the first-green turn.

```jsonl
{"turn": 1, "verify_exit": 1, "hidden_evaluator_exit": 1}
{"turn": 7, "verify_exit": 0, "hidden_evaluator_exit": 0}
{"turn": 8, "permission_denied": true}
```

The scorecard recognizes `verify_exit` / `verification_exit` and `hidden_exit` /
`hidden_evaluator_exit`. It also accepts boolean green markers such as `green` or
`public_hidden_green`.

## Interpretation

Use solution latency as a waste and stopping-behavior metric only when
`solution_latency_observable` is `true`.

If it is `false`, do not say the agent solved the task on a particular turn. Say
only that the final workspace was green and the first-green turn was not captured.
