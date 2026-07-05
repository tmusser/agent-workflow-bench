# Solution Latency

Semantic terminal state answers whether the final workspace was correct
against a raw terminal shape such as `max_turns`. Solution latency asks a
sharper question:

> On which turn did the run first become public + hidden green?

That requires per-turn evidence. The harness now records checkpoint rows when
the Claude print-mode helper can observe the run via `stream-json`; otherwise
it falls back to a conservative `mtime_polling` trace. Older bundles may still
have only final-state evidence, and those remain unobservable.

`mtime_polling` is best-effort. It only sees tracked-file timestamp changes, so
short runs or edits that touch only untracked files can be missed. When that
happens, keep `solution_latency_observable` false and do not infer first-green
post-hoc.

For separately measured E-arm audit cost and proof-attribution guidance, see
[docs/finalizer-attribution.md](docs/finalizer-attribution.md).

## Scorecard Fields

For each phase, the scorecard includes:

- `<phase>_actual_turns`
- `<phase>_first_green_turn`
- `<phase>_first_functional_green_turn`
- `<phase>_first_functional_green_wall_seconds`
- `<phase>_first_bench_ready_green_turn`
- `<phase>_first_bench_ready_green_wall_seconds`
- `<phase>_turns_after_first_green`
- `<phase>_turns_after_first_functional_green`
- `<phase>_turns_after_first_bench_ready_green`
- `<phase>_permission_denials_after_first_green`
- `<phase>_solution_latency_observable`
- `<phase>_solution_latency_source`
- `<phase>_solution_latency_note`

Phases use these prefixes:

- `initial`
- `full_resume`
- `stripped_resume`

The bundle-level scorecard also surfaces:

- `solution_latency_observable`
- `solution_latency_source`

## Emitted Artifact

The pilot wrapper now runs a best-effort post-processing step:

```bash
python -m benchmark_harness.emit_solution_latency annotate \
  --root "$ROOT_DIR" \
  --run-id "$RUN_ID"
```

For each collected phase, this writes `solution_latency.json` into that phase's
run directory before the eval bundle is rebuilt.

When checkpoint traces are present, `solution_latency.json` contains the first
functional and bench-ready green checkpoints:

```json
{
  "actual_turns": 21,
  "final_green": true,
  "final_hidden_exit": 0,
  "final_verify_exit": 0,
  "first_functional_green_turn": 7,
  "first_bench_ready_green_turn": 9,
  "note": "observed_from_per_turn_trace",
  "phase": "initial",
  "solution_latency_observable": true,
  "source": "stream_json",
  "turns_after_first_functional_green": 14,
  "turns_after_first_bench_ready_green": 12
}
```

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
  "source": "final_only_no_per_turn_trace",
  "turns_after_first_green": null
}
```

This is intentionally different from omitting the field. It says: the harness
looked for latency evidence and only had final-state evidence.

## Current Bundle Behavior

For bundles without per-turn traces:

- `actual_turns` can be read from `run_metrics.json` when present.
- `first_green_turn` remains empty.
- `first_functional_green_turn` remains empty.
- `first_bench_ready_green_turn` remains empty.
- `turns_after_first_green` remains empty.
- `turns_after_first_functional_green` remains empty.
- `turns_after_first_bench_ready_green` remains empty.
- `solution_latency_observable` is `false`.
- `solution_latency_source` is `final_only_no_per_turn_trace` for emitted
  summaries.
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
  "first_functional_green_turn": 7,
  "first_functional_green_wall_seconds": 12.5,
  "first_bench_ready_green_turn": 9,
  "first_bench_ready_green_wall_seconds": 19.2,
  "turns_after_first_green": 14,
  "turns_after_first_functional_green": 14,
  "turns_after_first_bench_ready_green": 12,
  "permission_denials_after_first_green": 3,
  "solution_latency_observable": true,
  "solution_latency_source": "stream_json",
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
{"turn": 1, "verify_exit": 1, "hidden_evaluator_exit": 1, "functional_green": false, "bench_ready_green": false}
{"turn": 7, "verify_exit": 0, "hidden_evaluator_exit": 0, "functional_green": true, "bench_ready_green": false}
{"turn": 9, "verify_exit": 0, "hidden_evaluator_exit": 0, "functional_green": true, "bench_ready_green": true}
```

The scorecard recognizes `verify_exit` / `verification_exit` and `hidden_exit` /
`hidden_evaluator_exit`. It also accepts boolean green markers such as
`functional_green`, `bench_ready_green`, `green`, or `public_hidden_green`.

For arm-specific bench-ready rules:

- `A-baseline`: bench-ready equals functional green.
- `E-ai-engineering-skills`: bench-ready requires functional green plus
  `VERIFY.md` and a valid `SKILL_RUNTIME_PROOF.md`.

## Interpretation

Use solution latency as a waste and stopping-behavior metric only when
`solution_latency_observable` is `true`.

If it is `false`, do not say the agent solved the task on a particular turn. Say
only that the final workspace was green and the first-green turn was not captured.
