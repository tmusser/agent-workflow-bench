# Artifact Usability Summary

Artifact usability summary is a deterministic, post-run artifact linter.

It answers a narrow question:

> Did the run leave basic, usable workflow artifacts?

It does **not** judge prose quality, correctness, or whether the artifacts helped a
fresh agent. Use fresh-session resume evaluation for that stronger question.

## What It Checks

The default expected artifacts are:

- `VERIFY.md`
- `HANDOFF.md`

Missing expected artifacts count against the usability floor. Extra known artifacts
such as `PLAN.md`, `SPEC.md`, `BUGS.md`, `FRESH_SESSION_REVIEW.md`, and
`BUGFIX_REVIEW.md` are summarized when present, but they do not define the default
usable/not-usable floor.

Checks are intentionally simple pattern checks. Examples:

| Artifact | Deterministic checks |
| --- | --- |
| `VERIFY.md` | mentions a verification command, result/status, and evidence/scope. |
| `HANDOFF.md` | mentions next/resume state, risk/uncertainty, and verification state. |
| `PLAN.md` | mentions steps and verification. |
| `SPEC.md` | mentions goal/contract/scope and acceptance/verification. |

This is a floor, not a judge. A passing artifact can still be misleading, and a
failing artifact can still contain useful prose. The point is to catch obvious
missing or empty artifacts before making stronger claims.

## Usage

Summarize one repository directly:

```bash
python -m benchmark_harness.artifact_usability summarize \
  --repo benchmark-data/workspaces/${RUN_ID}/repo \
  --run-id "$RUN_ID" \
  --phase initial \
  --out benchmark-data/runs/${RUN_ID}/artifact_usability_summary.json
```

Summarize a run using the benchmark layout:

```bash
python -m benchmark_harness.artifact_usability summarize-run \
  --run-id "$RUN_ID" \
  --phase initial
```

Resume phases are also supported:

```bash
python -m benchmark_harness.artifact_usability summarize-run --run-id "$RUN_ID" --phase full
python -m benchmark_harness.artifact_usability summarize-run --run-id "$RUN_ID" --phase stripped
```

Default output paths:

| Phase | Output |
| --- | --- |
| `initial` | `benchmark-data/runs/<RUN_ID>/artifact_usability_summary.json` |
| `full` | `benchmark-data/resume-runs/<RUN_ID>_full/artifact_usability_summary.json` |
| `stripped` | `benchmark-data/resume-runs/<RUN_ID>_stripped/artifact_usability_summary.json` |

Override the expected artifact floor when needed:

```bash
python -m benchmark_harness.artifact_usability summarize-run \
  --run-id "$RUN_ID" \
  --expected VERIFY.md,HANDOFF.md,BUGS.md
```

## Output Shape

```json
{
  "schema_version": 1,
  "run_id": "v07pilot_07-dashboard-export_E_r1",
  "phase": "initial",
  "expected_artifacts": ["VERIFY.md", "HANDOFF.md"],
  "artifacts": {
    "VERIFY.md": {
      "exists": true,
      "usable": true,
      "checks": {
        "has_verification_command": true,
        "has_result_status": true,
        "has_scope_or_evidence": true
      }
    }
  },
  "score": {
    "expected_present": 2,
    "expected_total": 2,
    "expected_usable": 2,
    "checks_passed": 6,
    "checks_total": 6,
    "usable": true
  }
}
```

## Interpretation

Use this as a quick artifact hygiene signal:

- `usable: true` means the expected artifacts met the deterministic floor.
- `usable: false` means expected artifacts are missing or failed basic checks.
- It should not be treated as proof that the artifacts are accurate, sufficient,
  or causally useful.

Good sequencing:

1. Functional and hidden evaluators answer whether the run solved the task.
2. Artifact usability answers whether basic durable context was left behind.
3. Fresh-session resume evaluation answers whether the durable context helped a new
   agent continue.
