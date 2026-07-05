# Solution Latency

Semantic terminal state answers whether the final workspace was correct
against a raw terminal shape such as `max_turns`. Solution latency asks a
sharper question:

> On which turn did the run first become public + hidden green?

That requires per-turn evidence. Existing bundles usually contain only
final workspace state and final verification results, so the scorecard must not
invent a first-green turn from final logs alone.

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

## Emitted Artifact

The pilot wrapper now runs a best-effort post-processing step:

```bash
python -m benchmark_harness.emit_solution_latency annotate \
  --root "$ROOT_DIR" \
  --run-id "$RUN_ID"
```

For each collected phase, this writes `solution_latency.json` into that phase's
run directory before the eval bundle is rebuilt.

For final-only runs without per-turn traces, the artifact records known final
state while keeping first-green latency unobservable:

```json
{
  "actual_turns": 21,
  "final_green": true,
  "final_hidden_exit": 0,
  "final_verify_exit": 0,
  "first_green_turn": null,
  "note": "final_only_no_per_turn_trace",
  "phase": "initial",
  "solution_latency_observable": false,
  "source": "final_collect_only",
  "turns_after_first_green": null
}
```

This is intentionally different from omitting the field. It says: the harness
looked for latency evidence and only had final-state evidence.

## Current Bundle Behavior

For bundles without per-turn traces:

- `actual_turns` can be read from `run_metrics.json` when present.
- `first_green_turn` remains empty.
- `turns_after_first_green` remains empty.
- `solution_latency_observable` is `false`.
- `solution_latency_note` is either `not_observable` for older bundles or
  `final_only_no_per_turn_trace` for bundles with emitted summaries.

This is intentional. It preserves the difference between:

- **known**: the final workspace is green;
- **unknown**: the exact turn where it first became green.

## Observable Bundle Inputs

The scorecard can compute first-green turn when a run directory includes one of
these optional files.

### `solution_latency.json`

```json
{
  "actual_turns": 21,
  "first_green_turn": 7,
  "turns_after_first_green": 14,
  "permission_denials_after_first_green": 3,
  "solution_latency_observable": true,
  "note": "computed_by_harness"
}
```

Only `first_green_turn` is required for an observable summary. When
`actual_turns` is present in `run_metrics.json`, `turns_after_first_green` can be
derived.

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
