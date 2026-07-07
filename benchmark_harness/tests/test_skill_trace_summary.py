from __future__ import annotations

import json
from pathlib import Path

from benchmark_harness.skill_trace_summary import (
    default_out_for_phase,
    main,
    summarize_repo,
    summarize_run,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_missing_skill_trace_is_valid_output(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    summary = summarize_repo(repo, run_id="run-1", phase="initial")

    assert summary.trace_present is False
    assert summary.evidence_level == "availability_only"
    assert summary.summary["valid_rows"] == 0
    assert summary.summary["invalid_rows"] == 0
    assert summary.declared_invoked_skills == []


def test_valid_skill_trace_summarizes_declared_events(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(
        repo / "SKILL_TRACE.jsonl",
        "\n".join(
            [
                json.dumps({"event_type": "skill_available", "skill_name": "mini-spec"}),
                json.dumps({"event_type": "skill_considered", "skill_name": "verify-contract"}),
                json.dumps({"event_type": "skill_invoked", "skill_name": "verify-contract"}),
                json.dumps({"event_type": "skill_skipped", "skill_name": "handoff"}),
            ]
        )
        + "\n",
    )

    summary = summarize_repo(repo, run_id="run-2", phase="initial")

    assert summary.trace_present is True
    assert summary.evidence_level == "agent_declared"
    assert summary.event_counts["skill_available"] == 1
    assert summary.event_counts["skill_considered"] == 1
    assert summary.event_counts["skill_invoked"] == 1
    assert summary.event_counts["skill_skipped"] == 1
    assert summary.declared_available_skills == ["mini-spec"]
    assert summary.declared_considered_skills == ["verify-contract"]
    assert summary.declared_invoked_skills == ["verify-contract"]
    assert summary.declared_skipped_skills == ["handoff"]
    assert summary.summary["valid_rows"] == 4


def test_malformed_jsonl_row_is_reported(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(
        repo / "SKILL_TRACE.jsonl",
        "\n".join(
            [
                json.dumps({"event_type": "skill_available", "skill_name": "mini-spec"}),
                '{"event_type": "skill_invoked", ',
            ]
        )
        + "\n",
    )

    summary = summarize_repo(repo)

    assert summary.trace_present is True
    assert summary.summary["valid_rows"] == 1
    assert summary.summary["invalid_rows"] == 1
    assert summary.invalid_rows[0].line_number == 2
    assert summary.invalid_rows[0].error.startswith("malformed_json:")


def test_unknown_event_type_is_invalid(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(
        repo / "SKILL_TRACE.jsonl",
        json.dumps({"event_type": "skill_runtime_hook", "skill_name": "verify-contract"}) + "\n",
    )

    summary = summarize_repo(repo)

    assert summary.summary["valid_rows"] == 0
    assert summary.summary["invalid_rows"] == 1
    assert summary.invalid_rows[0].error == "unknown_event_type: skill_runtime_hook"


def test_artifact_alignment_uses_verify_and_handoff_when_present(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(
        repo / "SKILL_TRACE.jsonl",
        "\n".join(
            [
                json.dumps({"event_type": "skill_invoked", "skill_name": "verify-contract"}),
                json.dumps({"event_type": "skill_invoked", "skill_name": "handoff"}),
            ]
        )
        + "\n",
    )
    _write(repo / "VERIFY.md", "verification\n")
    _write(repo / "HANDOFF.md", "handoff\n")

    summary = summarize_repo(repo)
    rows = {item.skill_name: item for item in summary.artifact_alignment}

    assert rows["verify-contract"].artifact_present is True
    assert rows["verify-contract"].declared_invoked is True
    assert rows["verify-contract"].aligned is True
    assert rows["handoff"].artifact_present is True
    assert rows["handoff"].declared_invoked is True
    assert rows["handoff"].aligned is True


def test_summarize_run_cli_writes_default_output(tmp_path: Path):
    root = tmp_path
    repo = root / "benchmark-data" / "workspaces" / "run-3" / "repo"
    repo.mkdir(parents=True)
    _write(repo / "SKILL_TRACE.jsonl", json.dumps({"event_type": "skill_invoked", "skill_name": "verify-contract"}) + "\n")

    exit_code = main(["summarize-run", "--root", str(root), "--run-id", "run-3", "--phase", "initial"])

    out = default_out_for_phase(root, "run-3", "initial")
    data = json.loads(out.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert data["trace_present"] is True
    assert data["declared_invoked_skills"] == ["verify-contract"]
    assert summarize_run(root, "run-3", phase="initial").declared_invoked_skills == ["verify-contract"]
