# Codex Runner Compatibility

This repository now has a first-class Codex-compatible smoke path, separate from the Claude-first `tools/pilot_smoke.sh` path.

The goal is runner compatibility, not a new benchmark result. Do not claim Codex-vs-Claude pass-rate comparisons until Codex runs have actually been piloted and bundled.

## What is supported

- `tools/pilot_codex_smoke.sh` prepares the same task workspaces as the existing smoke helper.
- It runs a configurable Codex CLI command in the initial, full-resume, and stripped-resume workspaces.
- It writes metadata-only `run_metrics.json` through `benchmark_harness.runner_metrics`.
- It writes existing `run_provenance.json` records before each Codex run.
- Existing collect steps, hidden evaluators, resume workspaces, bundles, and telemetry collection are reused.

## What is intentionally not claimed

- This does not prove Codex result quality.
- This does not make old Claude pilot rows comparable to new Codex pilot rows.
- This does not require network telemetry or content capture.
- This does not change the existing Claude smoke path.

## Basic usage

```bash
TASK_SLUG=01-support-sla-boundary \
ARM_SLUG=C-codex \
RUN_ID=v01pilot_01-sla-boundary_C_r1 \
./tools/pilot_codex_smoke.sh auto-c-r1
```

The default command shape is intentionally small:

```text
codex exec "<prompt contents>"
```

If your local Codex CLI needs a different shape, prefer a tiny wrapper script and point `CODEX_CMD` at it, or switch prompt delivery mode:

```bash
CODEX_CMD=codex \
CODEX_SUBCOMMAND=exec \
CODEX_PROMPT_MODE=stdin \
./tools/pilot_codex_smoke.sh run-initial-codex
```

Supported prompt modes:

| Mode | Behavior |
| --- | --- |
| `arg` | Pass prompt contents as the final command argument. |
| `stdin` | Pipe prompt contents to the command's stdin. |
| `file` | Pass the local prompt file path as the final command argument. |

## Useful environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `CODEX_CMD` | `codex` | Codex executable or wrapper script. |
| `CODEX_SUBCOMMAND` | `exec` | Optional subcommand appended after `CODEX_CMD`. |
| `CODEX_MODEL` | `codex-default` | Metadata model label. |
| `CODEX_PASS_MODEL_FLAG` | `0` | Set to `1` to pass `--model "$CODEX_MODEL"` to the command. |
| `CODEX_EFFORT` | `low` | Metadata effort label. |
| `CODEX_MAX_TURNS` | `20` | Metadata max-turn label. |
| `CODEX_PERMISSION_MODE` | `workspace-write` | Metadata permission label. |
| `CODEX_OUTPUT_FORMAT` | `text` | Set to `json` to parse safe token/timing metadata from stdout JSON. |
| `CODEX_EXTRA_ARGS` | empty | Space-separated extra CLI flags. Keep secrets and prompt text out of this value. |
| `CODEX_PROMPT_MODE` | `arg` | Prompt delivery mode: `arg`, `stdin`, or `file`. |
| `ENABLE_TELEMETRY` | unset | When truthy, collect local telemetry after each helper command. |

## Manual flow

```bash
./tools/pilot_codex_smoke.sh setup
./tools/pilot_codex_smoke.sh doctor
./tools/pilot_codex_smoke.sh init
./tools/pilot_codex_smoke.sh run-initial-codex
./tools/pilot_codex_smoke.sh collect-initial
./tools/pilot_codex_smoke.sh run-full-codex
./tools/pilot_codex_smoke.sh collect-full
./tools/pilot_codex_smoke.sh run-stripped-codex
./tools/pilot_codex_smoke.sh collect-stripped
```

## Metadata boundary

`run_metrics.json` records metadata only:

- provider / runner / model labels;
- exit codes;
- stdout/stderr byte and line counts;
- wall-clock seconds;
- safe token/timing fields parsed from JSON stdout when available.

It does not copy prompt bodies, stdout/stderr bodies, diffs, verification output, source files, fixture data, or full runner command strings.

## Telemetry

The Codex smoke script can use the local telemetry layer added in `docs/telemetry.md`:

```bash
ENABLE_TELEMETRY=1 ./tools/pilot_codex_smoke.sh auto-c-r1
```

Telemetry remains metadata-only and writes to `benchmark-data/runs/<RUN_ID>/telemetry.jsonl`.
