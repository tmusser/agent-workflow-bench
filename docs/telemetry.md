# Local Telemetry

The benchmark can collect local-only JSONL telemetry for pilot runs. This is a
lightweight diagnostic layer for understanding why a run succeeded, failed, or
became hard to resume.

It is intentionally not an observability platform.

## Privacy Boundary

Telemetry is metadata-only by default.

It does **not** copy:

- prompt bodies;
- model completions;
- stdout/stderr contents;
- diff contents;
- verification file contents;
- source file contents;
- fixture contents.

It may record:

- run id, task slug, arm slug, phase, and command label;
- model/effort/max-turn settings;
- token counts and timing fields when already exposed by `run_metrics.json`;
- local context-window pressure estimates from existing prompt files or usage metadata;
- file paths and byte sizes for known outputs and workflow artifacts;
- provenance hashes that the harness already records.

The implementation uses only Python stdlib and writes only local files.

## Enable Collection

Use the telemetry wrapper around the existing smoke helper:

```bash
ENABLE_TELEMETRY=1 \
TASK_SLUG=04-impossible-churn \
ARM_SLUG=A-baseline \
RUN_ID=v04pilot_04-bugfix_A_r1 \
./tools/pilot_smoke_with_telemetry.sh auto-a-r1
```

Telemetry is written to:

```text
benchmark-data/runs/<RUN_ID>/telemetry.jsonl
```

You can also collect telemetry after an existing run:

```bash
python -m benchmark_harness.telemetry collect-run --run-id "$RUN_ID" --root .
```

## Context Window Status

Telemetry emits a `context_window.status` event without making an extra LLM call.

The event prefers provider-reported `usage_input_tokens` when the Claude CLI
already exposes it through `run_metrics.json`. When usage tokens are unavailable,
it reads the local input prompt file only to count characters and estimates tokens
with a simple `chars / 4` heuristic. It never writes the prompt body to telemetry.

By default, the context window denominator is `200000` tokens. Override it for a
run when you want a different local assumption:

```bash
TELEMETRY_CONTEXT_WINDOW_TOKENS=200000 ENABLE_TELEMETRY=1 ./tools/pilot_smoke_with_telemetry.sh auto-a-r1
```

The status buckets are:

| Status | Used context estimate |
| --- | --- |
| `low` | `<50%` |
| `medium` | `>=50%` and `<75%` |
| `high` | `>=75%` and `<90%` |
| `critical` | `>=90%` |
| `unknown` | no usage tokens or local input file available |

This is a local pressure gauge, not a model-contract guarantee.

## Event Types

Current events include:

| Event | Meaning |
| --- | --- |
| `pilot_smoke.command` | The wrapper command and exit code. |
| `telemetry.collect_start` | Telemetry collection started. |
| `llm_call.summary` | Metadata from `run_metrics.json`, including model, timing, turn, and token fields when available. |
| `context_window.status` | Local context pressure estimate, based on existing usage metadata or prompt-file character counts. |
| `harness.provenance` | Prompt/wrapper paths and hashes from `run_provenance.json`. |
| `harness.outputs` | Known harness output files by path and byte size only. |
| `workflow.artifacts` | Known workflow artifact files by path and byte size only. |
| `telemetry.collect_end` | Telemetry collection finished. |

## Manual Event Emission

For small experiments, append a metadata-only event directly:

```bash
python -m benchmark_harness.telemetry emit \
  --path "benchmark-data/runs/${RUN_ID}/telemetry.jsonl" \
  --event-type "experiment.note" \
  --run-id "$RUN_ID" \
  --task-slug "$TASK_SLUG" \
  --arm-slug "$ARM_SLUG" \
  --field "note=reran_with_json_output"
```

Field names that look content-like, such as `prompt_body`, `stdout`, `stderr`,
`completion`, `secret`, or `file_content`, are rejected. Content-size metadata,
such as `stdout_bytes` or `usage_input_tokens`, is allowed.

This guard is field-name based, not a data-loss-prevention scanner. Do not pass
freeform prompt, completion, diff, verification, source, fixture, or secret values
through manual `--field` arguments under neutral names like `note` or `summary`.

## Why This Exists

The scorecard answers whether a run passed. Telemetry should help diagnose why.

Useful Task 8 design questions this can support:

- Did the model hit max turns before making the key compatibility fix?
- Did E-arm runs produce workflow artifacts early enough to help continuation?
- Did failing runs have weak provenance, missing artifacts, or large diffs?
- Did hidden failures correlate with context pressure, large stdout/stderr, high turn count, or missing verification artifacts?

Keep this layer boring. If a future telemetry field would be awkward to publish in
an eval bundle, it probably does not belong here.
