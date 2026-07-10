from __future__ import annotations

import json
from pathlib import Path

from benchmark_harness.scorecard import _trace_summary


def test_trace_summary_surfaces_provider_parity_and_overhead_fields(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    payload = {
        "trace_fidelity": "turn_event",
        "turns_observed": 3,
        "checkpoints_observed": 2,
        "checkpoint_coverage_complete": True,
        "stable_snapshot_coverage_complete": True,
        "checkpoint_evaluation_deferred": True,
        "checkpoint_boundary_resolution": "file_changing_tool_result_then_process_group_pause",
        "native_observation_unit": "assistant_turn_and_file_changing_tool_result",
        "checkpoint_snapshot_pause_seconds": 0.125,
        "checkpoint_evaluator_seconds": 3.5,
        "workspace_states_observed": 2,
        "workspace_states_skipped": 0,
    }
    (run_dir / "agent_turn_trace_summary.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    summary = _trace_summary(run_dir)
    assert summary["checkpoint_coverage_complete"] is True
    assert summary["stable_snapshot_coverage_complete"] is True
    assert summary["checkpoint_evaluation_deferred"] is True
    assert summary["checkpoint_boundary_resolution"] == payload["checkpoint_boundary_resolution"]
    assert summary["native_observation_unit"] == payload["native_observation_unit"]
    assert summary["checkpoint_snapshot_pause_seconds"] == 0.125
    assert summary["checkpoint_evaluator_seconds"] == 3.5
    assert summary["workspace_states_observed"] == 2
    assert summary["workspace_states_skipped"] == 0
