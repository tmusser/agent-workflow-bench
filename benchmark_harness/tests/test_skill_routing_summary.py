from __future__ import annotations

import json
from pathlib import Path

from benchmark_harness.skill_routing_summary import (
    default_out_for_phase,
    repo_for_phase,
    summarize_repo,
    summarize_skill_runtime_proof,
    write_summary,
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def valid_skill_runtime_proof() -> str:
    return """# Skill Runtime Proof

## Skill source
- Repo URL: https://github.com/tmusser/ai-engineering-skills
- Pinned commit SHA: 0123456789abcdef0123456789abcdef01234567
- Local path: /tmp/skills
- Install command: ./install.sh
- Install stdout/stderr path: benchmark-data/install.log

## Activation
- Agent CLI: claude
- Activation mechanism: plugin-dir
- Prompt wrapper path: arms/E-ai-engineering-skills.md
- Agent-visible skill files: skills/verify-contract/SKILL.md

## Pre-run availability check
- Command run: claude /help
- Result: pass

## During-run evidence
- Evidence path: VERIFY.md
"""


def test_summarize_repo_infers_skills_from_artifacts_and_validates_runtime_proof(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(repo / "SKILL_RUNTIME_PROOF.md", valid_skill_runtime_proof())
    write(repo / "VERIFY.md", "verification")
    write(repo / "HANDOFF.md", "handoff")
    write(repo / "BUGS.md", "bugs")

    summary = summarize_repo(repo, run_id="run-1", phase="initial", arm_slug="E-ai-engineering-skills")

    assert summary.claim_boundary == "inferred_from_artifacts_not_runtime_invocation_trace"
    assert summary.skill_runtime_proof.exists is True
    assert summary.skill_runtime_proof.valid is True
    assert summary.skill_runtime_proof.issues == []
    assert summary.inferred_skills["verify-contract"].present is True
    assert summary.inferred_skills["verify-contract"].evidence == ["VERIFY.md"]
    assert summary.inferred_skills["handoff"].present is True
    assert summary.inferred_skills["bug-capture"].present is True
    assert summary.inferred_skills["mini-spec"].present is False
    assert summary.summary["skills"] == ["bug-capture", "handoff", "verify-contract"]
    assert summary.summary["evidence_level"] == "runtime_proven"


def test_invalid_skill_runtime_proof_reports_issues(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(repo / "SKILL_RUNTIME_PROOF.md", "# incomplete proof\n")

    proof = summarize_skill_runtime_proof(repo)

    assert proof.exists is True
    assert proof.valid is False
    assert any(issue.startswith("missing marker:") for issue in proof.issues)


def test_absent_evidence_is_not_overclaimed(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    summary = summarize_repo(repo)

    assert summary.skill_runtime_proof.exists is False
    assert summary.skill_runtime_proof.valid is None
    assert summary.summary["skills_inferred"] == 0
    assert summary.summary["evidence_level"] == "absent"
    assert all(not item.present for item in summary.inferred_skills.values())


def test_write_summary_outputs_machine_readable_json(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(repo / "VERIFY.md", "verification")
    summary = summarize_repo(repo, run_id="run-2")

    out = write_summary(summary, tmp_path / "skill_routing_summary.json")
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["schema_version"] == 1
    assert data["run_id"] == "run-2"
    assert data["summary"]["skills"] == ["verify-contract"]
    assert data["summary"]["evidence_level"] == "present"


def test_phase_paths_follow_benchmark_layout(tmp_path: Path):
    run_id = "vtest"

    assert repo_for_phase(tmp_path, run_id, "initial") == tmp_path / "benchmark-data" / "workspaces" / run_id / "repo"
    assert repo_for_phase(tmp_path, run_id, "full") == tmp_path / "benchmark-data" / "resume-workspaces" / run_id / "full" / "repo"
    assert repo_for_phase(tmp_path, run_id, "stripped") == tmp_path / "benchmark-data" / "resume-workspaces" / run_id / "stripped" / "repo"
    assert default_out_for_phase(tmp_path, run_id, "initial") == tmp_path / "benchmark-data" / "runs" / run_id / "skill_routing_summary.json"
    assert default_out_for_phase(tmp_path, run_id, "stripped") == tmp_path / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "skill_routing_summary.json"
