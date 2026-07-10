from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one patch target, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# Resume phases must use the resume-specific hidden evaluator.
replace_once(
    "tools/pilot_codex_smoke.sh",
    '''  local root_dir prompt_abs stdout_abs stderr_abs exit_abs command_json_abs timing_abs observer_ran
''',
    '''  local root_dir prompt_abs stdout_abs stderr_abs exit_abs command_json_abs timing_abs observer_ran checkpoint_hidden_evaluator_module
''',
)
replace_once(
    "tools/pilot_codex_smoke.sh",
    '''  timing_abs="${root_dir}/${out_dir}/codex_checkpoint_timing.json"
  observer_ran=false
''',
    '''  timing_abs="${root_dir}/${out_dir}/codex_checkpoint_timing.json"
  observer_ran=false
  checkpoint_hidden_evaluator_module="$HIDDEN_EVALUATOR_MODULE"
  if [[ "$label" != "initial" && -n "$RESUME_HIDDEN_EVALUATOR_MODULE" ]]; then
    checkpoint_hidden_evaluator_module="$RESUME_HIDDEN_EVALUATOR_MODULE"
  fi
''',
)
replace_once(
    "tools/pilot_codex_smoke.sh",
    '''      --hidden-evaluator-module "$HIDDEN_EVALUATOR_MODULE" \\
''',
    '''      --hidden-evaluator-module "$checkpoint_hidden_evaluator_module" \\
''',
)

# Exactness is conditional on complete, stable snapshot coverage.
replace_once(
    "benchmark_harness/codex_solution_latency_observer.py",
    '''            "checkpoint_coverage_complete": coverage_complete,
            "stable_snapshot_coverage_complete": stable_live_snapshots,
            "workspace_states_observed": len(captures),
''',
    '''            "checkpoint_coverage_complete": coverage_complete,
            "stable_snapshot_coverage_complete": stable_live_snapshots,
            "item_solution_latency_observable": coverage_complete,
            "checkpoint_boundary_resolution": "provider_item_completed_then_process_group_pause",
            "workspace_states_observed": len(captures),
''',
)
replace_once(
    "benchmark_harness/codex_solution_latency_observer.py",
    '''            "stable_snapshot_coverage_complete": stable_live_snapshots,
        },
''',
    '''            "stable_snapshot_coverage_complete": stable_live_snapshots,
            "checkpoint_boundary_resolution": "provider_item_completed_then_process_group_pause",
        },
''',
)

# Surface the boundary-resolution metadata in scorecards.
replace_once(
    "benchmark_harness/scorecard.py",
    '''    "stable_snapshot_coverage_complete",
    "workspace_states_observed",
''',
    '''    "stable_snapshot_coverage_complete",
    "checkpoint_boundary_resolution",
    "workspace_states_observed",
''',
)
for prefix in ("initial", "full", "stripped"):
    replace_once(
        "benchmark_harness/scorecard.py",
        f'''    "{prefix}_stable_snapshot_coverage_complete",\n    "{prefix}_workspace_states_observed",\n''',
        f'''    "{prefix}_stable_snapshot_coverage_complete",\n    "{prefix}_checkpoint_boundary_resolution",\n    "{prefix}_workspace_states_observed",\n''',
    )
replace_once(
    "benchmark_harness/scorecard.py",
    '''        "stable_snapshot_coverage_complete": summary.get("stable_snapshot_coverage_complete"),
        "workspace_states_observed": summary.get("workspace_states_observed"),
''',
    '''        "stable_snapshot_coverage_complete": summary.get("stable_snapshot_coverage_complete"),
        "checkpoint_boundary_resolution": summary.get("checkpoint_boundary_resolution"),
        "workspace_states_observed": summary.get("workspace_states_observed"),
''',
)

# Tighten docs: exact at provider-item snapshot resolution, not instruction-level time.
docs = Path("docs/solution-latency.md")
text = docs.read_text(encoding="utf-8")
old = '''Snapshot evaluation happens after Codex exits so hidden checks do not steer the agent or
consume its context. The runner briefly pauses the Codex process group only while copying
a stable workspace snapshot and records that pause separately from evaluator time.

Do not call all work after functional green "waste" automatically.
'''
new = '''Snapshot evaluation happens after Codex exits so hidden checks do not steer the agent or
consume its context. The runner briefly pauses the Codex process group only while copying
a stable workspace snapshot and records that pause separately from evaluator time.

The resolution is a completed provider-item boundary followed by process-group pause. This
is the strongest observation available from the current Codex stream, but it is not an
instruction-level timestamp: a very small event-to-pause scheduling race remains possible.
Describe the result as the first evaluator-green captured provider item, and require
`checkpoint_coverage_complete=true` before treating it as the first observed green state.

Do not call all work after functional green "waste" automatically.
'''
if old not in text:
    raise RuntimeError("docs boundary paragraph not found")
docs.write_text(text.replace(old, new, 1), encoding="utf-8")

# Extend the end-to-end assertions.
test = Path("benchmark_harness/tests/test_codex_solution_latency_e2e.py")
text = test.read_text(encoding="utf-8")
text = text.replace(
    '''    assert summary["checkpoint_coverage_complete"] is (os.name == "posix")
''',
    '''    assert summary["checkpoint_coverage_complete"] is (os.name == "posix")
    assert summary["item_solution_latency_observable"] is (os.name == "posix")
    assert summary["checkpoint_boundary_resolution"] == "provider_item_completed_then_process_group_pause"
''',
)
test.write_text(text, encoding="utf-8")
