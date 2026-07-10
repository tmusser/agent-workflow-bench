from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one patch target, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# The integration patch adds an optional provider item to a legacy helper. Keep
# the optional parameter after all required parameters so the signature remains valid.
replace_once(
    "benchmark_harness/solution_latency_observer.py",
    '''    assistant_message_id: str | None,
    wall_seconds: float,
    provider_item_index: int | None = None,
    verify_exit: int,
    hidden_exit: int,
    functional_green: bool,
    bench_ready_green: bool,
    permission_denials_delta: int,
    checkpoint_eval_errors: list[str],
) -> dict[str, Any]:
''',
    '''    assistant_message_id: str | None,
    wall_seconds: float,
    verify_exit: int,
    hidden_exit: int,
    functional_green: bool,
    bench_ready_green: bool,
    permission_denials_delta: int,
    checkpoint_eval_errors: list[str],
    provider_item_index: int | None = None,
) -> dict[str, Any]:
''',
)

replace_once(
    "benchmark_harness/codex_solution_latency_observer.py",
    '''    snapshot_root: Path
    pause_seconds: float
''',
    '''    snapshot_root: Path
    pause_seconds: float
    process_group_paused: bool
''',
)
replace_once(
    "benchmark_harness/codex_solution_latency_observer.py",
    '''        pause_seconds=pause_seconds,
    )
''',
    '''        pause_seconds=pause_seconds,
        process_group_paused=paused,
    )
''',
)
replace_once(
    "benchmark_harness/codex_solution_latency_observer.py",
    '''                pause_seconds=0.0,
            )
''',
    '''                pause_seconds=0.0,
                process_group_paused=True,
            )
''',
)
replace_once(
    "benchmark_harness/codex_solution_latency_observer.py",
    '''    coverage_complete = distinct_states_skipped == 0
''',
    '''    stable_live_snapshots = all(
        item.process_group_paused for item in captures if item.trigger != "final_workspace"
    )
    coverage_complete = distinct_states_skipped == 0 and stable_live_snapshots
''',
)
replace_once(
    "benchmark_harness/codex_solution_latency_observer.py",
    '''            "checkpoint_coverage_complete": coverage_complete,
            "workspace_states_observed": len(captures),
''',
    '''            "checkpoint_coverage_complete": coverage_complete,
            "stable_snapshot_coverage_complete": stable_live_snapshots,
            "workspace_states_observed": len(captures),
''',
)
replace_once(
    "benchmark_harness/codex_solution_latency_observer.py",
    '''            "checkpoint_coverage_complete": coverage_complete,
        },
''',
    '''            "checkpoint_coverage_complete": coverage_complete,
            "stable_snapshot_coverage_complete": stable_live_snapshots,
        },
''',
)

# Tests use positional construction; add the explicit stability flag.
test_path = Path("benchmark_harness/tests/test_codex_solution_latency_observer.py")
text = test_path.read_text(encoding="utf-8")
text = text.replace(
    '''                pause_seconds=0.01,
            )
''',
    '''                pause_seconds=0.01,
                process_group_paused=True,
            )
''',
)
text = text.replace(
    '''    capture = CapturedWorkspace(1, 1, "file_change_completed", 1.0, "fp", temp_root, snapshot_root, 0.0)
''',
    '''    capture = CapturedWorkspace(1, 1, "file_change_completed", 1.0, "fp", temp_root, snapshot_root, 0.0, True)
''',
)
test_path.write_text(text, encoding="utf-8")

# Surface the stable-capture boundary in scorecards too.
replace_once(
    "benchmark_harness/scorecard.py",
    '''    "checkpoint_coverage_complete",
    "workspace_states_observed",
''',
    '''    "checkpoint_coverage_complete",
    "stable_snapshot_coverage_complete",
    "workspace_states_observed",
''',
)
for prefix in ("initial", "full", "stripped"):
    replace_once(
        "benchmark_harness/scorecard.py",
        f'''    "{prefix}_checkpoint_coverage_complete",\n    "{prefix}_workspace_states_observed",\n''',
        f'''    "{prefix}_checkpoint_coverage_complete",\n    "{prefix}_stable_snapshot_coverage_complete",\n    "{prefix}_workspace_states_observed",\n''',
    )
replace_once(
    "benchmark_harness/scorecard.py",
    '''        "checkpoint_coverage_complete": summary.get("checkpoint_coverage_complete"),
        "workspace_states_observed": summary.get("workspace_states_observed"),
''',
    '''        "checkpoint_coverage_complete": summary.get("checkpoint_coverage_complete"),
        "stable_snapshot_coverage_complete": summary.get("stable_snapshot_coverage_complete"),
        "workspace_states_observed": summary.get("workspace_states_observed"),
''',
)
