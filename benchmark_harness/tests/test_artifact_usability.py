from __future__ import annotations

import json
from pathlib import Path

from benchmark_harness.artifact_usability import (
    default_out_for_phase,
    evaluate_artifact,
    repo_for_phase,
    summarize_repo,
    write_summary,
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_evaluate_verify_artifact_uses_deterministic_checks(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(
        repo / "VERIFY.md",
        "# Verification\n\nCommand: `python -m pytest -q`\n\nResult: PASS\n\nEvidence: regression coverage added.\n",
    )

    result = evaluate_artifact(repo, "VERIFY.md", expected=True)

    assert result.exists is True
    assert result.usable is True
    assert result.checks == {
        "has_verification_command": True,
        "has_result_status": True,
        "has_scope_or_evidence": True,
    }


def test_missing_expected_artifact_counts_as_not_usable(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    summary = summarize_repo(repo, run_id="run-1", expected_artifacts=["VERIFY.md", "HANDOFF.md"])

    assert summary.score["expected_present"] == 0
    assert summary.score["expected_total"] == 2
    assert summary.score["usable"] is False
    assert summary.artifacts["VERIFY.md"].exists is False
    assert summary.artifacts["HANDOFF.md"].exists is False


def test_summarize_repo_scores_expected_artifacts_only_for_usable_floor(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(
        repo / "VERIFY.md",
        "# Verification\n\nRun `./VERIFY.sh`. Result: passed. Evidence: hidden regression check.\n",
    )
    write(
        repo / "HANDOFF.md",
        "# Handoff\n\nNext: continue from current patch. Risk: fixture trap. Verification: VERIFY.sh passed.\n",
    )
    write(repo / "PLAN.md", "# Plan\n\nStep 1: patch. Verify with tests.\n")

    summary = summarize_repo(repo, run_id="run-2", phase="initial")

    assert summary.score["artifacts_checked"] == 3
    assert summary.score["expected_present"] == 2
    assert summary.score["expected_usable"] == 2
    assert summary.score["usable"] is True
    assert summary.artifacts["PLAN.md"].expected is False
    assert summary.artifacts["PLAN.md"].usable is True


def test_write_summary_outputs_json(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(repo / "VERIFY.md", "Command: pytest. Result: pass. Evidence: regression.\n")
    write(repo / "HANDOFF.md", "Next step. Risk noted. Verification passed.\n")
    summary = summarize_repo(repo, run_id="run-3")

    out = write_summary(summary, tmp_path / "artifact_usability_summary.json")
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["schema_version"] == 1
    assert data["run_id"] == "run-3"
    assert data["score"]["usable"] is True
    assert data["artifacts"]["VERIFY.md"]["checks"]["has_result_status"] is True


def test_phase_paths_follow_benchmark_layout(tmp_path: Path):
    run_id = "vtest"

    assert repo_for_phase(tmp_path, run_id, "initial") == tmp_path / "benchmark-data" / "workspaces" / run_id / "repo"
    assert repo_for_phase(tmp_path, run_id, "full") == tmp_path / "benchmark-data" / "resume-workspaces" / run_id / "full" / "repo"
    assert repo_for_phase(tmp_path, run_id, "stripped") == tmp_path / "benchmark-data" / "resume-workspaces" / run_id / "stripped" / "repo"
    assert default_out_for_phase(tmp_path, run_id, "initial") == tmp_path / "benchmark-data" / "runs" / run_id / "artifact_usability_summary.json"
    assert default_out_for_phase(tmp_path, run_id, "full") == tmp_path / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "artifact_usability_summary.json"
