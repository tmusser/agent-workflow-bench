from __future__ import annotations

import json
import textwrap
from pathlib import Path

from benchmark_harness import scorecard, skill_runtime_recovery
from benchmark_harness.evaluators.task5_hidden_evaluator import _paragraph_has_unnegated_affirmative_overclaim
from benchmark_harness.evidence_status import infer_exit_from_text
from benchmark_harness.validate_skill_runtime_proof import validate


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _proof(run_id: str, *, agent_cli: str = "Codex CLI", env: str = "SKILL_PLUGIN_DIR=/tmp/skills") -> str:
    return textwrap.dedent(
        f"""\
        # Skill Runtime Proof

        ## Run
        - Run ID: {run_id}
        - Arm: E-ai-engineering-skills
        - Task: 05-fake-data-analysis
        - Repeat: r1

        ## Skill source
        - Repo URL: https://example.com/repo.git
        - Pinned commit SHA: 0123456789abcdef0123456789abcdef01234567
        - Local path: /tmp/skills
        - Install command: ./benchmark_harness/scripts/pin_skill_repos.sh local_plugins
        - Install stdout/stderr path: benchmark-data/skill-repos/pinned_skill_repos.csv

        ## Activation
        - Agent CLI: {agent_cli}
        - Activation mechanism: pinned local skill files made available through runtime context
        - Prompt wrapper path: arms/E-ai-engineering-skills.md
        - Agent-visible skill files: skills/verify-contract/SKILL.md
        - Environment variables relevant to skill loading: {env}

        ## Pre-run availability check
        - Command run: test -f .benchmark/SKILL_RUNTIME_CONTEXT.md
        - Result: available
        - Evidence path: .benchmark/SKILL_RUNTIME_CONTEXT.md

        ## During-run evidence
        - Invocation evidence level: agent_declared
        - Did the agent mention or invoke the skill? yes
        - Evidence: SKILL_TRACE.jsonl
        - Notes: agent-declared only

        ## Post-run caveat
        - Could a bad result be due to the skill not being loaded? no
        - Reviewer notes: context present
        """
    )


def _context(run_id: str) -> str:
    return textwrap.dedent(
        f"""\
        # Skill Runtime Context
        - Repo URL: https://example.com/repo.git
        - Pinned commit SHA: 0123456789abcdef0123456789abcdef01234567
        - Local plugin path: /tmp/skills
        - Agent-visible plugin path: /tmp/skills
        - Pre-run availability check command: test -f /tmp/skills/PINNED_SKILL_REPO.md
        - Pre-run availability check result: available
        - Pre-run availability evidence path: .benchmark/SKILL_RUNTIME_CONTEXT.md
        - Task slug: 05-fake-data-analysis
        - Arm slug: E-ai-engineering-skills
        - Run ID: {run_id}
        """
    )


def _make_recovery_run(tmp_path: Path, run_id: str, hidden_text: str) -> tuple[Path, Path, Path]:
    run_dir = tmp_path / "runs" / run_id
    workspace = tmp_path / "workspaces" / run_id / "repo"
    prompt = run_dir / "prompt.md"
    _write(prompt, "Create `SKILL_RUNTIME_PROOF.md`.\n")
    _write(run_dir / "verification_final.txt", "3 passed in 0.10s\n")
    _write(run_dir / "hidden_evaluator_final.txt", hidden_text)
    _write(run_dir / "diff.patch", "diff --git a/a.py b/a.py\n")
    _write(run_dir / "diff_stat.txt", "1 file changed\n")
    _write(run_dir / "codex_stdout.txt", '{"type":"turn.completed"}\n')
    _write(run_dir / "codex_stderr.txt", "")
    _write(
        run_dir / "run_metrics.json",
        json.dumps({"runner": "codex-cli", "provider": "codex", "actual_turns": 1, "runner_exit_code": 0}),
    )
    _write(run_dir / "run_provenance.json", json.dumps({"model": "gpt-5.4-mini"}))
    _write(workspace / ".benchmark" / "SKILL_RUNTIME_CONTEXT.md", _context(run_id))
    _write(workspace / "SKILL_RUNTIME_PROOF.md", _proof(run_id))
    return run_dir, workspace, prompt


def test_structured_task7_json_is_green() -> None:
    assert infer_exit_from_text(json.dumps({"overall_green": True, "errors": []}), "hidden") == 0


def test_structured_task6_key_values_are_green() -> None:
    text = "hidden_contract_pass: true\nfresh_review_present: true\nresume_request_complete: true\nerrors:\n"
    assert infer_exit_from_text(text, "hidden") == 0


def test_e_functional_failure_keeps_artifact_status_separate(tmp_path: Path) -> None:
    run_dir, workspace, prompt = _make_recovery_run(
        tmp_path,
        "task5-e",
        "HIDDEN CONTRACT FAILED: missing denominator inconsistency\n",
    )
    result = skill_runtime_recovery.build_skill_runtime_recovery(
        run_dir=run_dir,
        workspace_root=workspace,
        prompt_file=prompt,
        run_id="task5-e",
        task_slug="05-fake-data-analysis",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        collect_exit_code=1,
    )
    assert result["functional_status"] == "failed"
    assert result["artifact_status"] == "passed"
    assert result["classification"] == "functional_failure"


def test_unknown_evaluator_output_is_harness_failure(tmp_path: Path) -> None:
    run_dir, workspace, prompt = _make_recovery_run(tmp_path, "unknown-e", "unrecognized output\n")
    result = skill_runtime_recovery.build_skill_runtime_recovery(
        run_dir=run_dir,
        workspace_root=workspace,
        prompt_file=prompt,
        run_id="unknown-e",
        task_slug="05-fake-data-analysis",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        collect_exit_code=1,
    )
    assert result["functional_status"] == "unknown"
    assert result["classification"] == "harness_failure"


def test_codex_proof_rejects_claude_specific_claims(tmp_path: Path) -> None:
    path = tmp_path / "SKILL_RUNTIME_PROOF.md"
    path.write_text(_proof("r1", agent_cli="Claude Code", env="CLAUDE_PLUGIN_DIR=/tmp/skills"), encoding="utf-8")
    issues = validate(path, expected_agent_cli="codex-cli")
    assert any("does not match expected runner family codex" in issue for issue in issues)
    assert any("CLAUDE_PLUGIN_DIR" in issue for issue in issues)


def test_scorecard_prefers_provenance_and_recognizes_c_run_ids() -> None:
    assert scorecard._arm_slug_from_evidence(
        "v07pilot_07-dashboard-export_C_r1",
        {"arm_slug": "C-codex"},
        {"canonical_arm_slug": "C-codex"},
    ) == "C-codex"
    assert scorecard._arm_slug_from_run_id("v07pilot_07-dashboard-export_C_r1") == "C-codex"


def test_task5_avoid_claiming_is_negated() -> None:
    assert not _paragraph_has_unnegated_affirmative_overclaim(
        "Avoid claiming that the campaign caused the lift."
    )
