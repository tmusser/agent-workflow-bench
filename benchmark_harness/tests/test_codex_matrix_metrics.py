from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from benchmark_harness import codex_matrix_metrics as matrix_metrics


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_metrics(
    *,
    run_id: str,
    task_slug: str | None = None,
    arm_slug: str | None = None,
    phase: str | None = None,
    base_run_id: str | None = None,
    model_label: str | None = None,
    model: str | None = None,
    provider: str = "codex",
    runner: str = "codex-cli",
    actual_turns: int | None = None,
    input_tokens: int | None = None,
    cached_input_tokens: int | None = None,
    output_tokens: int | None = None,
    reasoning_output_tokens: int | None = None,
    wall_clock_seconds: float | None = None,
    exit_code: int | None = None,
    label: str | None = None,
) -> dict[str, object]:
    data: dict[str, object] = {
        "run_id": run_id,
        "provider": provider,
        "runner": runner,
    }
    if task_slug is not None:
        data["task_slug"] = task_slug
    if arm_slug is not None:
        data["arm_slug"] = arm_slug
    if phase is not None:
        data["phase"] = phase
    if base_run_id is not None:
        data["base_run_id"] = base_run_id
    if model_label is not None:
        data["model_label"] = model_label
    if model is not None:
        data["model"] = model
    if actual_turns is not None:
        data["actual_turns"] = actual_turns
    if input_tokens is not None:
        data["input_tokens"] = input_tokens
    if cached_input_tokens is not None:
        data["cached_input_tokens"] = cached_input_tokens
    if output_tokens is not None:
        data["output_tokens"] = output_tokens
    if reasoning_output_tokens is not None:
        data["reasoning_output_tokens"] = reasoning_output_tokens
    if wall_clock_seconds is not None:
        data["wall_clock_seconds"] = wall_clock_seconds
    if exit_code is not None:
        data["exit_code"] = exit_code
    if label is not None:
        data["label"] = label
    return data


def _make_recovery(
    *,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    phase: str,
    classification: str,
    public_status: str,
    functional_green: bool,
    verification_exit: int,
    hidden_evaluator_exit: int,
    task_attempted: bool,
    initial_not_ready_present: bool = False,
    stop_after_initial: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "task_slug": task_slug,
        "arm_slug": arm_slug,
        "phase": phase,
        "classification": classification,
        "public_status": public_status,
        "functional_green": functional_green,
        "verification_exit": verification_exit,
        "hidden_evaluator_exit": hidden_evaluator_exit,
        "task_attempted": task_attempted,
        "initial_not_ready_present": initial_not_ready_present,
        "stop_after_initial": stop_after_initial,
        "skill_runtime_context_present": False,
        "skill_runtime_context_valid": False,
        "skill_runtime_proof_present": False,
        "skill_runtime_proof_valid": False,
    }


def _run_metrics_path(repo_root: Path, run_dir: str) -> Path:
    return repo_root / "benchmark-data" / run_dir / "run_metrics.json"


def test_summary_reports_missing_c_rows_and_compares_arms_without_shared_model_label(tmp_path: Path):
    repo_root = tmp_path / "repo"
    c_run = _run_metrics_path(repo_root, "runs/v01pilot_01-sla-boundary_C_r1")
    e_run = _run_metrics_path(repo_root, "runs/v01pilot_01-sla-boundary_E_r1")

    _write_json(
        c_run,
        _make_metrics(
            run_id="v01pilot_01-sla-boundary_C_r1",
            task_slug="01-support-sla-boundary",
            arm_slug="C-codex",
            phase="initial",
            base_run_id="v01pilot_01-sla-boundary_C_r1",
            model_label="codex-mini",
            actual_turns=2,
            input_tokens=100,
            cached_input_tokens=20,
            output_tokens=30,
            reasoning_output_tokens=5,
            wall_clock_seconds=1.5,
            exit_code=0,
        ),
    )
    _write_json(
        e_run,
        _make_metrics(
            run_id="v01pilot_01-sla-boundary_E_r1",
            task_slug="01-support-sla-boundary",
            arm_slug="E-ai-engineering-skills",
            phase="initial",
            base_run_id="v01pilot_01-sla-boundary_E_r1",
            model_label="gpt-5.4-mini",
            actual_turns=3,
            input_tokens=200,
            cached_input_tokens=50,
            output_tokens=40,
            reasoning_output_tokens=10,
            wall_clock_seconds=2.75,
            exit_code=0,
        ),
    )

    rows, summary = matrix_metrics.summarize_matrix(
        repo_root=repo_root,
        tasks=["01-support-sla-boundary"],
        arms=["C-codex", "E-ai-engineering-skills"],
        phases=["initial", "full_resume", "stripped_resume"],
    )

    assert summary["scheduled_rows"] == 6
    assert summary["rows_found"] == 2
    assert summary["rows_missing"] == 4
    assert summary["valid_completed_rows"] == 2
    assert summary["failed_rows"] == 0
    assert summary["blocked_rows"] == 0
    assert summary["actual_turns"] == 5
    assert summary["input_tokens"] == 300
    assert summary["cached_input_tokens"] == 70
    assert summary["uncached_input_tokens"] == 230
    assert summary["output_tokens"] == 70
    assert summary["reasoning_output_tokens"] == 15
    assert summary["billableish_tokens"] == 300

    c_row = next(row for row in rows if row["arm_slug"] == "C-codex" and row["phase"] == "initial")
    e_row = next(row for row in rows if row["arm_slug"] == "E-ai-engineering-skills" and row["phase"] == "initial")
    missing_c_full = next(row for row in rows if row["arm_slug"] == "C-codex" and row["phase"] == "full_resume")

    assert c_row["model_label"] == "codex-mini"
    assert e_row["model_label"] == "gpt-5.4-mini"
    assert c_row["uncached_input_tokens"] == 80
    assert c_row["billableish_tokens"] == 110
    assert e_row["uncached_input_tokens"] == 150
    assert e_row["billableish_tokens"] == 190
    assert missing_c_full["status"] == "missing"
    assert missing_c_full["expected_run_id"] == "v01pilot_01-sla-boundary_C_r1"


def test_summary_infers_task_arm_phase_from_run_id_and_path_when_metadata_incomplete(tmp_path: Path):
    repo_root = tmp_path / "repo"
    run_dir = repo_root / "benchmark-data" / "resume-runs" / "v01pilot_01-sla-boundary_C_r1_full"
    _write_json(
        run_dir / "run_metrics.json",
        {
            "run_id": "v01pilot_01-sla-boundary_C_r1_full",
            "provider": "codex",
            "runner": "codex-cli",
            "model": "gpt-5.4-mini",
            "actual_turns": 1,
            "input_tokens": 12,
            "cached_input_tokens": 4,
            "output_tokens": 6,
            "reasoning_output_tokens": 2,
            "wall_clock_seconds": 1.25,
            "exit_code": 0,
        },
    )

    rows, summary = matrix_metrics.summarize_matrix(
        repo_root=repo_root,
        tasks=["01-support-sla-boundary"],
        arms=["C-codex"],
        phases=["full_resume"],
    )

    assert summary["scheduled_rows"] == 1
    assert summary["rows_found"] == 1
    assert summary["rows_missing"] == 0
    row = rows[0]
    assert row["task_slug"] == "01-support-sla-boundary"
    assert row["arm_slug"] == "C-codex"
    assert row["phase"] == "full_resume"
    assert row["run_id"] == "v01pilot_01-sla-boundary_C_r1_full"
    assert row["base_run_id"] == "v01pilot_01-sla-boundary_C_r1"
    assert row["model_label"] == "gpt-5.4-mini"
    assert row["actual_turns"] == 1
    assert row["uncached_input_tokens"] == 8
    assert row["billableish_tokens"] == 14


def test_summary_uses_canonical_json_metadata_when_present(tmp_path: Path):
    repo_root = tmp_path / "repo"
    run_dir = repo_root / "benchmark-data" / "runs" / "not-a-real-run"
    _write_json(
        run_dir / "run_metrics.json",
        {
            "run_id": "v01pilot_01-sla-boundary_E_r1",
            "base_run_id": "v01pilot_01-sla-boundary_E_r1",
            "task_slug": "01-support-sla-boundary",
            "arm_slug": "E-ai-engineering-skills",
            "phase": "initial",
            "provider": "codex",
            "runner": "codex-cli",
            "model_label": "gpt-5.4-mini",
            "label": "stripped resume",
            "actual_turns": 4,
            "input_tokens": 90,
            "cached_input_tokens": 30,
            "output_tokens": 10,
            "reasoning_output_tokens": 3,
            "wall_clock_seconds": 4.5,
            "exit_code": 0,
        },
    )

    rows, summary = matrix_metrics.summarize_matrix(
        repo_root=repo_root,
        tasks=["01-support-sla-boundary"],
        arms=["E-ai-engineering-skills"],
        phases=["initial"],
    )

    assert summary["rows_found"] == 1
    row = rows[0]
    assert row["run_id"] == "v01pilot_01-sla-boundary_E_r1"
    assert row["base_run_id"] == "v01pilot_01-sla-boundary_E_r1"
    assert row["phase"] == "initial"
    assert row["actual_turns"] == 4
    assert row["uncached_input_tokens"] == 60
    assert row["billableish_tokens"] == 70


def test_summary_uses_matrix_summary_csv_expectations(tmp_path: Path):
    repo_root = tmp_path / "repo"
    summary_csv = repo_root / "expected.csv"
    _write_text(
        summary_csv,
        "\n".join(
            [
                "task_slug,arm_slug,phase,expected_run_id",
                "01-support-sla-boundary,C-codex,initial,v01pilot_01-sla-boundary_C_r1",
                "01-support-sla-boundary,E-ai-engineering-skills,initial,v01pilot_01-sla-boundary_E_r1",
            ]
        )
        + "\n",
    )
    _write_json(
        _run_metrics_path(repo_root, "runs/v01pilot_01-sla-boundary_C_r1"),
        _make_metrics(
            run_id="v01pilot_01-sla-boundary_C_r1",
            task_slug="01-support-sla-boundary",
            arm_slug="C-codex",
            phase="initial",
            model_label="codex-mini",
            actual_turns=1,
            input_tokens=10,
            output_tokens=5,
            wall_clock_seconds=1.0,
            exit_code=0,
        ),
    )
    _write_json(
        _run_metrics_path(repo_root, "runs/v01pilot_01-sla-boundary_E_r1"),
        _make_metrics(
            run_id="v01pilot_01-sla-boundary_E_r1",
            task_slug="01-support-sla-boundary",
            arm_slug="E-ai-engineering-skills",
            phase="initial",
            model_label="gpt-5.4-mini",
            actual_turns=2,
            input_tokens=20,
            output_tokens=10,
            wall_clock_seconds=2.0,
            exit_code=0,
        ),
    )

    rows, summary = matrix_metrics.summarize_matrix(
        repo_root=repo_root,
        tasks=[],
        arms=[],
        phases=[],
        summary_csv=summary_csv,
    )

    assert summary["scheduled_rows"] == 2
    assert summary["rows_found"] == 2
    assert all(row["status"] == "completed" for row in rows)


def test_summary_reclassifies_stale_c_skill_context_failure_to_completed(tmp_path: Path):
    repo_root = tmp_path / "repo"
    run_dir = repo_root / "benchmark-data" / "runs" / "v03pilot_03-refund-grain_C_g54mini_r1"
    _write_json(
        run_dir / "run_metrics.json",
        _make_metrics(
            run_id="v03pilot_03-refund-grain_C_g54mini_r1",
            task_slug="03-refund-grain",
            arm_slug="C-codex",
            phase="initial",
            model_label="gpt-5.4-mini",
            actual_turns=1,
            input_tokens=100,
            cached_input_tokens=20,
            output_tokens=30,
            reasoning_output_tokens=5,
            wall_clock_seconds=1.25,
            exit_code=0,
        ),
    )
    _write_text(run_dir / "verification_final.txt", "3 passed in 0.34s\n")
    _write_text(run_dir / "hidden_evaluator_final.txt", "Hidden Task 4 evaluator passed\n")
    _write_json(
        run_dir / "skill_runtime_recovery.json",
        _make_recovery(
            run_id="v03pilot_03-refund-grain_C_g54mini_r1",
            task_slug="03-refund-grain",
            arm_slug="C-codex",
            phase="initial",
            classification="skill_context_failure",
            public_status="failed: skill context",
            functional_green=True,
            verification_exit=0,
            hidden_evaluator_exit=0,
            task_attempted=True,
        ),
    )

    rows, summary = matrix_metrics.summarize_matrix(
        repo_root=repo_root,
        tasks=["03-refund-grain"],
        arms=["C-codex"],
        phases=["initial"],
    )

    assert summary["scheduled_rows"] == 1
    assert summary["rows_found"] == 1
    assert summary["rows_missing"] == 0
    assert summary["valid_completed_rows"] == 1
    assert summary["failed_rows"] == 0
    assert summary["blocked_rows"] == 0
    assert rows[0]["status"] == "completed"
    assert rows[0]["row_state"] == "completed"


def test_summary_marks_c_hidden_failure_as_failed_and_keeps_resume_rows_missing(tmp_path: Path):
    repo_root = tmp_path / "repo"
    run_dir = repo_root / "benchmark-data" / "runs" / "v04pilot_04-bugfix_C_g54mini_r1"
    _write_json(
        run_dir / "run_metrics.json",
        _make_metrics(
            run_id="v04pilot_04-bugfix_C_g54mini_r1",
            task_slug="04-impossible-churn",
            arm_slug="C-codex",
            phase="initial",
            model_label="gpt-5.4-mini",
            actual_turns=1,
            input_tokens=120,
            cached_input_tokens=30,
            output_tokens=40,
            reasoning_output_tokens=8,
            wall_clock_seconds=2.5,
            exit_code=0,
        ),
    )
    _write_text(run_dir / "verification_final.txt", "3 passed in 0.34s\n")
    _write_text(run_dir / "hidden_evaluator_final.txt", "HIDDEN CONTRACT FAILED: impossible churn rows were found\n")
    _write_text(run_dir / "INITIAL_NOT_READY.txt", "Initial run is not ready for resume testing.\n")
    _write_json(
        run_dir / "skill_runtime_recovery.json",
        _make_recovery(
            run_id="v04pilot_04-bugfix_C_g54mini_r1",
            task_slug="04-impossible-churn",
            arm_slug="C-codex",
            phase="initial",
            classification="skill_context_failure",
            public_status="failed: skill context",
            functional_green=False,
            verification_exit=0,
            hidden_evaluator_exit=1,
            task_attempted=True,
            initial_not_ready_present=True,
            stop_after_initial=False,
        ),
    )

    rows, summary = matrix_metrics.summarize_matrix(
        repo_root=repo_root,
        tasks=["04-impossible-churn"],
        arms=["C-codex"],
        phases=["initial", "full_resume", "stripped_resume"],
    )

    assert summary["scheduled_rows"] == 3
    assert summary["rows_found"] == 1
    assert summary["rows_missing"] == 2
    assert summary["valid_completed_rows"] == 0
    assert summary["failed_rows"] == 1
    assert summary["blocked_rows"] == 0
    assert rows[0]["status"] == "failed"
    assert rows[0]["row_state"] == "failed"
    missing_rows = [row for row in rows if row["status"] == "missing"]
    assert [row["phase"] for row in missing_rows] == ["full_resume", "stripped_resume"]


def test_summary_keeps_e_skill_context_failure_blocked(tmp_path: Path):
    repo_root = tmp_path / "repo"
    run_dir = repo_root / "benchmark-data" / "runs" / "v01pilot_01-sla-boundary_E_r1"
    _write_json(
        run_dir / "run_metrics.json",
        _make_metrics(
            run_id="v01pilot_01-sla-boundary_E_r1",
            task_slug="01-support-sla-boundary",
            arm_slug="E-ai-engineering-skills",
            phase="initial",
            model_label="gpt-5.4-mini",
            actual_turns=1,
            input_tokens=80,
            output_tokens=20,
            wall_clock_seconds=1.75,
            exit_code=0,
        ),
    )
    _write_json(
        run_dir / "skill_runtime_recovery.json",
        _make_recovery(
            run_id="v01pilot_01-sla-boundary_E_r1",
            task_slug="01-support-sla-boundary",
            arm_slug="E-ai-engineering-skills",
            phase="initial",
            classification="skill_context_failure",
            public_status="blocked: skill context before task attempt",
            functional_green=False,
            verification_exit=0,
            hidden_evaluator_exit=0,
            task_attempted=False,
            stop_after_initial=True,
        ),
    )

    rows, summary = matrix_metrics.summarize_matrix(
        repo_root=repo_root,
        tasks=["01-support-sla-boundary"],
        arms=["E-ai-engineering-skills"],
        phases=["initial"],
    )

    assert summary["scheduled_rows"] == 1
    assert summary["rows_found"] == 1
    assert summary["rows_missing"] == 0
    assert summary["valid_completed_rows"] == 0
    assert summary["failed_rows"] == 0
    assert summary["blocked_rows"] == 1
    assert rows[0]["status"] == "blocked"
    assert rows[0]["row_state"] == "blocked"


def test_backfill_refuses_when_codex_evidence_is_absent(tmp_path: Path):
    repo_root = tmp_path / "repo"
    run_dir = repo_root / "benchmark-data" / "runs" / "v01pilot_01-sla-boundary_C_r1"
    run_dir.mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        matrix_metrics.backfill_run_metrics(
            run_dir=run_dir,
            repo_root=repo_root,
            task_slug="01-support-sla-boundary",
            arm_slug="C-codex",
            phase="initial",
        )


def test_backfill_is_idempotent_when_evidence_present(tmp_path: Path):
    repo_root = tmp_path / "repo"
    run_dir = repo_root / "benchmark-data" / "runs" / "v01pilot_01-sla-boundary_C_r1"
    _write_json(run_dir / "run_provenance.json", {"model": "gpt-5.4-mini"})
    _write_text(
        run_dir / "codex_stdout.txt",
        "\n".join(
            [
                json.dumps({"type": "turn.started"}),
                json.dumps({"type": "item.completed", "item": {"type": "tool_call", "name": "shell", "id": "call_1"}}),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 120,
                            "cached_input_tokens": 40,
                            "output_tokens": 30,
                            "reasoning_output_tokens": 10,
                        },
                    }
                ),
            ]
        )
        + "\n",
    )
    _write_text(run_dir / "codex_stderr.txt", "")
    _write_text(run_dir / "codex_exit_code.txt", "0\n")

    first = matrix_metrics.backfill_run_metrics(
        run_dir=run_dir,
        repo_root=repo_root,
        task_slug="01-support-sla-boundary",
        arm_slug="C-codex",
        phase="initial",
    )
    first_text = (run_dir / "run_metrics.json").read_text(encoding="utf-8")

    second = matrix_metrics.backfill_run_metrics(
        run_dir=run_dir,
        repo_root=repo_root,
        task_slug="01-support-sla-boundary",
        arm_slug="C-codex",
        phase="initial",
    )
    second_text = (run_dir / "run_metrics.json").read_text(encoding="utf-8")

    assert first_text == second_text
    assert first["schema_version"] == 1
    assert first["base_run_id"] == "v01pilot_01-sla-boundary_C_r1"
    assert first["model_label"] == "gpt-5.4-mini"
    assert first["actual_turns"] == 1
    assert first["input_tokens"] == 120
    assert first["cached_input_tokens"] == 40
    assert first["uncached_input_tokens"] == 80
    assert first["output_tokens"] == 30
    assert first["reasoning_output_tokens"] == 10
    assert first["total_tokens"] == 150
    assert first["stdout_path"] == "benchmark-data/runs/v01pilot_01-sla-boundary_C_r1/codex_stdout.txt"
    assert second["stdout_path"] == first["stdout_path"]


def test_existing_e_r4_metrics_remain_readable(tmp_path: Path):
    repo_root = tmp_path / "repo"
    _write_json(
        _run_metrics_path(repo_root, "resume-runs/v03pilot_03-refund-grain_E_g54mini_r4_full"),
        {
            "run_id": "v03pilot_03-refund-grain_E_g54mini_r4",
            "label": "full resume",
            "arm_slug": "E-ai-engineering-skills",
            "model": "gpt-5.4-mini",
            "provider": "codex",
            "runner": "codex-cli",
            "actual_turns": 1,
            "input_tokens": 435554,
            "cached_input_tokens": 412032,
            "output_tokens": 15155,
            "reasoning_output_tokens": 11118,
            "wall_clock_seconds": 243.755,
            "exit_code": 0,
        },
    )

    rows, summary = matrix_metrics.summarize_matrix(
        repo_root=repo_root,
        tasks=["03-refund-grain"],
        arms=["E-ai-engineering-skills"],
        phases=["full_resume"],
    )

    assert summary["rows_found"] == 1
    row = rows[0]
    assert row["run_id"] == "v03pilot_03-refund-grain_E_g54mini_r4"
    assert row["phase"] == "full_resume"
    assert row["actual_turns"] == 1
    assert row["uncached_input_tokens"] == 23522
    assert row["billableish_tokens"] == 38677
