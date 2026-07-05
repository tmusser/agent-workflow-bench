from __future__ import annotations

import json
from pathlib import Path

import pytest

import benchmark_harness.run_provenance as run_provenance


def _write(path: Path, text: str = "ok\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_task7_files(root: Path) -> None:
    _write(root / "arms" / "B-strong-no-skill-task7.md", "# wrapper\n")
    _write(root / "arms" / "B-baseline.md", "# baseline wrapper\n")
    _write(root / "tasks" / "07-dashboard-export-scope-pressure" / "starter_repo" / "TASK.md", "# task\n")
    _write(root / "benchmark_harness" / "protocols" / "FRESH_SESSION_PROMPT_TASK7.md", "# prompt\n")


def test_run_provenance_cli_writes_alias_metadata(tmp_path: Path):
    _make_task7_files(tmp_path)
    out = tmp_path / "run_provenance.json"

    assert (
        run_provenance.main(
            [
                "--out",
                str(out),
                "--root",
                str(tmp_path),
                "--run-id",
                "v07pilot_07-dashboard-export_B_r1_full",
                "--task-slug",
                "07-dashboard-export-scope-pressure",
                "--arm-slug",
                "B-baseline",
                "--arm-wrapper",
                "arms/B-strong-no-skill-task7.md",
                "--task-prompt",
                "tasks/07-dashboard-export-scope-pressure/starter_repo/TASK.md",
                "--resume-prompt",
                "benchmark_harness/protocols/FRESH_SESSION_PROMPT_TASK7.md",
                "--label",
                "full resume",
                "--model",
                "sonnet",
                "--effort",
                "low",
                "--max-turns",
                "60",
                "--permission-mode",
                "acceptEdits",
                "--output-format",
                "json",
                "--pressure-level",
                "medium",
                "--pressure-seed",
                "7",
                "--pressure-tokens-estimated",
                "3000",
                "--context-window-tokens",
                "20000",
                "--estimated-context-utilization",
                "15.0",
                "--pressure-target-pct",
                "0.15",
            ]
        )
        == 0
    )

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["arm_slug"] == "B-baseline"
    assert data["requested_arm_slug"] == "B-baseline"
    assert data["resolved_arm_slug"] == "B-strong-no-skill"
    assert data["canonical_arm_slug"] == "B-strong-no-skill"
    assert data["arm_slug_mismatch"] is True
    assert data["alias_applied"] is True
    assert data["alias_reason"] == "Task 7 legacy B label maps to task-specific strong no-skill wrapper"
    assert data["context_mode"] == "full resume"
    assert data["pressure_level"] == "medium"
    assert data["pressure_seed"] == 7
    assert data["pressure_tokens_estimated"] == 3000
    assert data["context_window_tokens"] == 20000
    assert data["estimated_context_utilization"] == 15.0
    assert data["pressure_target_pct"] == 0.15
    assert data["arm_wrapper_path"] == "arms/B-strong-no-skill-task7.md"
    assert data["task_prompt_path"] == "tasks/07-dashboard-export-scope-pressure/starter_repo/TASK.md"
    assert data["resume_prompt_path"] == "benchmark_harness/protocols/FRESH_SESSION_PROMPT_TASK7.md"
    assert len(data["arm_wrapper_sha256"]) == 64
    assert len(data["task_prompt_sha256"]) == 64
    assert len(data["resume_prompt_sha256"]) == 64


def test_run_provenance_rejects_task7_baseline_wrapper(tmp_path: Path):
    _make_task7_files(tmp_path)

    with pytest.raises(ValueError, match="Task 7 B runs must resolve to arms/B-strong-no-skill-task7.md"):
        run_provenance.build_run_provenance(
            root_dir=tmp_path,
            run_id="v07pilot_07-dashboard-export_B_r1_full",
            task_slug="07-dashboard-export-scope-pressure",
            arm_slug="B-strong-no-skill",
            arm_wrapper="arms/B-baseline.md",
            task_prompt="tasks/07-dashboard-export-scope-pressure/starter_repo/TASK.md",
            resume_prompt="benchmark_harness/protocols/FRESH_SESSION_PROMPT_TASK7.md",
            label="full resume",
            model="sonnet",
            effort="low",
            max_turns=60,
            permission_mode="acceptEdits",
            output_format="json",
        )
