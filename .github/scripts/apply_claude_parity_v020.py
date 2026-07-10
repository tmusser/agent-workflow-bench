from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one patch target, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_after(path: str, anchor: str, addition: str) -> None:
    replace_once(path, anchor, anchor + addition)


# Release metadata.
replace_once(
    "pyproject.toml",
    'version = "0.1.0"\n',
    'version = "0.2.0"\n',
)

# Claude smoke runner: hardened observer, phase-correct evaluator, checkpoint cap,
# and process-only timing just like the Codex path.
replace_once(
    "tools/pilot_smoke_legacy.sh",
    '''CLAUDE_MAX_TURNS="${CLAUDE_MAX_TURNS:-20}"
CLAUDE_PERMISSION_MODE="${CLAUDE_PERMISSION_MODE:-dangerously-skip-permissions}"
''',
    '''CLAUDE_MAX_TURNS="${CLAUDE_MAX_TURNS:-20}"
CLAUDE_MAX_CHECKPOINTS="${CLAUDE_MAX_CHECKPOINTS:-32}"
CLAUDE_PERMISSION_MODE="${CLAUDE_PERMISSION_MODE:-dangerously-skip-permissions}"
''',
)
replace_once(
    "tools/pilot_smoke_legacy.sh",
    '''  local root_dir prompt_abs stdout_abs stderr_abs
''',
    '''  local root_dir prompt_abs stdout_abs stderr_abs timing_abs checkpoint_hidden_evaluator_module
''',
)
replace_once(
    "tools/pilot_smoke_legacy.sh",
    '''  stderr_abs="${root_dir}/${out_dir}/claude_stderr.txt"

  local exit_abs exit_code
''',
    '''  stderr_abs="${root_dir}/${out_dir}/claude_stderr.txt"
  timing_abs="${root_dir}/${out_dir}/claude_checkpoint_timing.json"
  checkpoint_hidden_evaluator_module="$HIDDEN_EVALUATOR_MODULE"
  if [[ "$label" != "initial" && -n "$RESUME_HIDDEN_EVALUATOR_MODULE" ]]; then
    checkpoint_hidden_evaluator_module="$RESUME_HIDDEN_EVALUATOR_MODULE"
  fi

  local exit_abs exit_code
''',
)
replace_once(
    "tools/pilot_smoke_legacy.sh",
    '''    python -m benchmark_harness.solution_latency_observer run
''',
    '''    python -m benchmark_harness.claude_solution_latency_observer run
''',
)
replace_once(
    "tools/pilot_smoke_legacy.sh",
    '''    --hidden-evaluator-module "$HIDDEN_EVALUATOR_MODULE"
    --mode "$observer_mode"
''',
    '''    --hidden-evaluator-module "$checkpoint_hidden_evaluator_module"
    --mode "$observer_mode"
    --max-checkpoints "$CLAUDE_MAX_CHECKPOINTS"
''',
)
replace_once(
    "tools/pilot_smoke_legacy.sh",
    '''  end_ns="$(python - <<'PY'
import time
print(time.time_ns())
PY
)"
  echo "$exit_code" > "$exit_abs"
''',
    '''  end_ns="$(python - <<'PY'
import time
print(time.time_ns())
PY
)"
  if [[ -f "$timing_abs" ]]; then
    read -r start_ns end_ns < <(python - "$timing_abs" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(data["process_start_ns"], data["process_end_ns"])
PY
)
  fi
  echo "$exit_code" > "$exit_abs"
''',
)

# Scorecard: expose provider-neutral parity and overhead fields for all phases.
replace_once(
    "benchmark_harness/scorecard.py",
    '''    "checkpoint_boundary_resolution",
    "workspace_states_observed",
''',
    '''    "checkpoint_boundary_resolution",
    "checkpoint_evaluation_deferred",
    "native_observation_unit",
    "checkpoint_snapshot_pause_seconds",
    "checkpoint_evaluator_seconds",
    "workspace_states_observed",
''',
)
for prefix in ("initial", "full", "stripped"):
    replace_once(
        "benchmark_harness/scorecard.py",
        f'''    "{prefix}_checkpoint_boundary_resolution",\n    "{prefix}_workspace_states_observed",\n''',
        f'''    "{prefix}_checkpoint_boundary_resolution",\n    "{prefix}_checkpoint_evaluation_deferred",\n    "{prefix}_native_observation_unit",\n    "{prefix}_checkpoint_snapshot_pause_seconds",\n    "{prefix}_checkpoint_evaluator_seconds",\n    "{prefix}_workspace_states_observed",\n''',
    )
replace_once(
    "benchmark_harness/scorecard.py",
    '''        "checkpoint_boundary_resolution": summary.get("checkpoint_boundary_resolution"),
        "workspace_states_observed": summary.get("workspace_states_observed"),
''',
    '''        "checkpoint_boundary_resolution": summary.get("checkpoint_boundary_resolution"),
        "checkpoint_evaluation_deferred": summary.get("checkpoint_evaluation_deferred"),
        "native_observation_unit": summary.get("native_observation_unit"),
        "checkpoint_snapshot_pause_seconds": summary.get("checkpoint_snapshot_pause_seconds"),
        "checkpoint_evaluator_seconds": summary.get("checkpoint_evaluator_seconds"),
        "workspace_states_observed": summary.get("workspace_states_observed"),
''',
)

# README release badge, capability entry point, and concise provider-parity blurb.
replace_once(
    "README.md",
    '''[![Version v0.1.0](https://img.shields.io/badge/version-v0.1.0-informational)](https://github.com/tmusser/agent-workflow-bench/releases/tag/v0.1.0)
''',
    '''[![Version v0.2.0](https://img.shields.io/badge/version-v0.2.0-informational)](https://github.com/tmusser/agent-workflow-bench/releases/tag/v0.2.0)
''',
)
insert_after(
    "README.md",
    '''For agent-declared trace evidence, see [docs/skill-trace.md](docs/skill-trace.md).
''',
    '''For Claude/Codex harness parity and claim boundaries, see [docs/capabilities.md](docs/capabilities.md).

### Provider-native observability

The Claude and Codex harnesses now apply the same evidence contract: stable workspace snapshots, hidden evaluation deferred until the agent exits, phase-correct resume evaluators, explicit coverage completeness, and separate functional-green versus bench-ready-green tails. Claude reports at its native turn/tool-result resolution; Codex reports at provider-item resolution. These units are not treated as interchangeable.
''',
)

# Solution-latency docs: replace the obsolete live-evaluation description with
# the v0.2 stable/deferred contract while preserving fallback caveats.
replace_once(
    "docs/solution-latency.md",
    '''That requires per-turn evidence. The harness now records checkpoint rows when
the Claude print-mode helper can observe the run via `stream-json`; otherwise
it falls back to a conservative `mtime_polling` trace. Older bundles may still
have only final-state evidence, and those remain unobservable.
''',
    '''That requires provider-native intermediate evidence. In v0.2.0, both the Claude
and Codex paths capture stable workspace snapshots during the agent run and evaluate
them only after the agent exits. Claude prefers `stream-json`; when unavailable it
falls back to conservative `mtime_polling`. Older bundles may still have only final-
state evidence, and those remain unobservable.
''',
)
replace_once(
    "docs/solution-latency.md",
    '''`mtime_polling` is best-effort. It only sees tracked-file timestamp changes, so
short runs or edits that touch only untracked files can be missed. When that
happens, keep `solution_latency_observable` false and do not infer first-green
post-hoc.
''',
    '''`mtime_polling` is best-effort sampling and cannot prove complete intermediate
coverage. The hardened fallback snapshots whole-workspace changes rather than only
running evaluators against the live tree, but intermediate states can still be missed.
It therefore keeps `checkpoint_coverage_complete` and `solution_latency_observable`
false. Do not infer first-green post-hoc.
''',
)

# Scorecard docs: provider-neutral observability columns.
scorecard_docs = Path("docs/scorecard.md")
scorecard_text = scorecard_docs.read_text(encoding="utf-8")
addition = '''

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
'''
if "## Provider observability fields" not in scorecard_text:
    scorecard_docs.write_text(scorecard_text.rstrip() + addition + "\n", encoding="utf-8")
