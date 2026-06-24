from __future__ import annotations

import json
import tarfile
import textwrap
from pathlib import Path

from benchmark_harness import scorecard


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def valid_skill_runtime_proof(run_id: str, arm: str = "E") -> str:
    return textwrap.dedent(
        f"""\
        # Skill Runtime Proof

        ## Run
        - Run ID: {run_id}
        - Arm: {arm}
        - Task: 05-fake-data - Fake Data Campaign Lift
        - Repeat: 1

        ## Skill source
        - Repo URL: https://example.com/repo.git
        - Pinned commit SHA: 0123456789abcdef0123456789abcdef01234567
        - Local path: /tmp/skills/repo
        - Install command: cp -R /tmp/skills/repo ~/.claude/skills/repo
        - Install stdout/stderr path: benchmark-data/runs/{run_id}/install.txt

        ## Activation
        - Agent CLI: claude
        - Activation mechanism: skill directory mounted before run
        - Prompt wrapper path: arms/E-ai-engineering-skills.md
        - Agent-visible skill files: ~/.claude/skills/repo/README.md

        ## Pre-run availability check
        - Command run: test -f ~/.claude/skills/repo/README.md
        - Result: pass
        - Evidence path: benchmark-data/runs/{run_id}/skill_available.txt

        ## During-run evidence
        - Did the agent mention or invoke the skill? yes
        - Evidence: benchmark-data/runs/{run_id}/stdout.txt
        - Notes: none
        """
    )


def make_bundle(tmp_path: Path, run_id: str, files: dict[str, str], *, bundle_type: str = "eval") -> Path:
    root = tmp_path / f"{run_id}_bundle"
    for rel_path, text in files.items():
        write(root / rel_path, text)

    bundle = tmp_path / f"{run_id}-{bundle_type}-bundle.tar.gz"
    with tarfile.open(bundle, "w:gz") as tar:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                tar.add(path, arcname=path.relative_to(root).as_posix())
    return bundle


def base_initial_run_files(
    run_id: str,
    *,
    hidden: str = "pass",
    skill_runtime_proof: str | None = None,
) -> dict[str, str]:
    files = {
        f"benchmark-data/runs/{run_id}/run_workspace_manifest.json": json.dumps(
            {"dest_repo": f"benchmark-data/workspaces/{run_id}/repo"},
            indent=2,
        )
        + "\n",
        f"benchmark-data/runs/{run_id}/diff.patch": (
            "diff --git a/src/churncalc/metrics.py b/src/churncalc/metrics.py\n"
            "--- a/src/churncalc/metrics.py\n"
            "+++ b/src/churncalc/metrics.py\n"
            "@@\n"
            "-old\n"
            "+new\n"
        ),
        f"benchmark-data/runs/{run_id}/diff_stat.txt": "1 file changed, 1 insertion(+), 1 deletion(-)\n",
        f"benchmark-data/runs/{run_id}/verification_final.txt": (
            "March enterprise churn row:\n"
            "{'month': '2024-03', 'plan': 'enterprise', 'starting_customers': 6, 'cancellations': 5, 'churn_rate': 0.8333333333333334}\n"
            "No impossible churn detected\n"
            "...                                                                      [100%]\n"
            "3 passed in 0.34s\n"
        ),
        f"benchmark-data/runs/{run_id}/claude_stdout.txt": "",
        f"benchmark-data/runs/{run_id}/claude_stderr.txt": "",
    }
    if hidden == "pass":
        files[f"benchmark-data/runs/{run_id}/hidden_evaluator_final.txt"] = "Hidden Task 4 evaluator passed\n"
    elif hidden == "fail":
        files[f"benchmark-data/runs/{run_id}/hidden_evaluator_final.txt"] = (
            "HIDDEN CONTRACT FAILED: impossible churn rows were found\n"
        )
    if skill_runtime_proof is not None:
        files[f"benchmark-data/workspaces/{run_id}/repo/SKILL_RUNTIME_PROOF.md"] = skill_runtime_proof
    return files


def base_initial_fail_run_files(
    run_id: str,
    *,
    skill_runtime_proof: str | None = None,
    workflow_artifacts: dict[str, str] | None = None,
    failure_reason: str = "missing required blocker themes: denominator inconsistency, leakage or post-treatment field risk",
) -> dict[str, str]:
    files = {
        f"benchmark-data/runs/{run_id}/run_workspace_manifest.json": json.dumps(
            {"dest_repo": f"benchmark-data/workspaces/{run_id}/repo"},
            indent=2,
        )
        + "\n",
        f"benchmark-data/runs/{run_id}/diff.patch": (
            "diff --git a/src/churncalc/metrics.py b/src/churncalc/metrics.py\n"
            "--- a/src/churncalc/metrics.py\n"
            "+++ b/src/churncalc/metrics.py\n"
            "@@\n"
            "-old\n"
            "+new\n"
        ),
        f"benchmark-data/runs/{run_id}/diff_stat.txt": "1 file changed, 1 insertion(+), 1 deletion(-)\n",
        f"benchmark-data/runs/{run_id}/verification_final.txt": (
            "March enterprise churn row:\n"
            "{'month': '2024-03', 'plan': 'enterprise', 'starting_customers': 6, 'cancellations': 5, 'churn_rate': 0.8333333333333334}\n"
            "No impossible churn detected\n"
            "...                                                                      [100%]\n"
            "3 passed in 0.34s\n"
        ),
        f"benchmark-data/runs/{run_id}/hidden_evaluator_final.txt": f"HIDDEN CONTRACT FAILED: {failure_reason}\n",
        f"benchmark-data/runs/{run_id}/INITIAL_NOT_READY.txt": (
            "Initial run is not ready for resume testing.\n\n"
            "verify_exit=0\n"
            "hidden_evaluator_exit=1\n"
            "diff_bytes=15381\n\n"
            "Do not create/use full or stripped resume workspaces from this run unless intentionally testing failure recovery.\n"
        ),
        f"benchmark-data/runs/{run_id}/claude_stdout.txt": "",
        f"benchmark-data/runs/{run_id}/claude_stderr.txt": "",
        f"benchmark-data/workspaces/{run_id}/repo/TASK.md": "# task\n",
    }
    if skill_runtime_proof is not None:
        files[f"benchmark-data/workspaces/{run_id}/repo/SKILL_RUNTIME_PROOF.md"] = skill_runtime_proof
    if workflow_artifacts:
        for rel_path, text in workflow_artifacts.items():
            files[f"benchmark-data/workspaces/{run_id}/repo/{rel_path}"] = text
    return files


def base_resume_files(run_id: str, *, tag: str) -> dict[str, str]:
    return {
        f"benchmark-data/resume-runs/{run_id}_{tag}/diff.patch": (
            "diff --git a/tests/test_impossible_churn_bug.py b/tests/test_impossible_churn_bug.py\n"
            "--- a/tests/test_impossible_churn_bug.py\n"
            "+++ b/tests/test_impossible_churn_bug.py\n"
            "@@\n"
            "+def test_active_interval_mapping():\n"
            "+    assert cancellation_count == 1\n"
            "+    assert plan_history_rows == 2\n"
        ),
        f"benchmark-data/resume-runs/{run_id}_{tag}/diff_stat.txt": "1 file changed, 3 insertions(+)\n",
        f"benchmark-data/resume-runs/{run_id}_{tag}/verification.txt": (
            "March enterprise churn row:\n"
            "{'month': '2024-03', 'plan': 'enterprise', 'starting_customers': 6, 'cancellations': 5, 'churn_rate': 0.8333333333333334}\n"
            "No impossible churn detected\n"
            "...                                                                      [100%]\n"
            "4 passed in 0.35s\n"
        ),
        f"benchmark-data/resume-runs/{run_id}_{tag}/hidden_evaluator.txt": "Hidden Task 4 evaluator passed\n",
    }


def test_scorecard_summarizes_baseline_bundle(tmp_path: Path):
    run_id = "v04pilot_04-bugfix_A_r1"
    files = {
        **base_initial_run_files(run_id),
        **base_resume_files(run_id, tag="full"),
        **base_resume_files(run_id, tag="stripped"),
        f"benchmark-data/workspaces/{run_id}/repo/TASK.md": "# task\n",
        f"benchmark-data/resume-workspaces/{run_id}/stripped/metadata/stripped_artifacts_manifest.json": json.dumps(
            {
                "removed": [],
                "kept_required_outputs": [],
                "skipped": [],
                "ambiguous_not_removed": [],
                "dry_run": False,
            },
            indent=2,
        )
        + "\n",
    }
    bundle = make_bundle(tmp_path, run_id, files)

    row = scorecard.score_bundle(bundle)

    assert row["run_id"] == run_id
    assert row["arm_slug"] == "A-baseline"
    assert row["initial_verify_exit"] == 0
    assert row["initial_hidden_exit"] == 0
    assert row["initial_green"] is True
    assert row["initial_diff_files"] == 1
    assert row["initial_diff_bytes"] > 0
    assert row["skill_runtime_proof_present"] is False
    assert row["skill_runtime_proof_valid"] is False
    assert row["workflow_artifacts_present"] is False
    assert row["workflow_artifacts"] == ""
    assert row["stripped_removed_artifacts"] == ""
    assert row["artifact_mechanism_active"] is False
    assert row["full_resume_green"] is True
    assert row["stripped_resume_green"] is True
    assert row["full_added_regression_test"] is True
    assert row["stripped_added_regression_test"] is True
    assert row["agent_side_verification_claim"] == "unknown"


def test_scorecard_detects_artifacts_and_skill_proof(tmp_path: Path):
    run_id = "v04pilot_04-bugfix_E_r3"
    files = {
        **base_initial_run_files(run_id, skill_runtime_proof=valid_skill_runtime_proof(run_id)),
        **base_resume_files(run_id, tag="full"),
        **base_resume_files(run_id, tag="stripped"),
        f"benchmark-data/workspaces/{run_id}/repo/TASK.md": "# task\n",
        f"benchmark-data/workspaces/{run_id}/repo/BUGS.md": "bugs\n",
        f"benchmark-data/workspaces/{run_id}/repo/VERIFY.md": "verify\n",
        f"benchmark-data/workspaces/{run_id}/repo/HANDOFF.md": "handoff\n",
        f"benchmark-data/runs/{run_id}/claude_stdout.txt": "I ran VERIFY.sh and pytest -q; both passed.\n",
        f"benchmark-data/resume-workspaces/{run_id}/stripped/metadata/stripped_artifacts_manifest.json": json.dumps(
            {
                "removed": ["BUGS.md", "VERIFY.md", "HANDOFF.md", "SKILL_RUNTIME_PROOF.md"],
                "kept_required_outputs": [],
                "skipped": [],
                "ambiguous_not_removed": [],
                "dry_run": False,
            },
            indent=2,
        )
        + "\n",
    }
    bundle = make_bundle(tmp_path, run_id, files)

    row = scorecard.score_bundle(bundle)

    assert row["run_id"] == run_id
    assert row["arm_slug"] == "E-ai-engineering-skills"
    assert row["skill_runtime_proof_present"] is True
    assert row["skill_runtime_proof_valid"] is True
    assert row["workflow_artifacts_present"] is True
    assert row["workflow_artifacts"] == "BUGS.md;VERIFY.md;HANDOFF.md;SKILL_RUNTIME_PROOF.md"
    assert row["stripped_removed_artifacts"] == "BUGS.md;VERIFY.md;HANDOFF.md;SKILL_RUNTIME_PROOF.md"
    assert row["artifact_mechanism_active"] is True
    assert row["agent_side_verification_claim"] == "claimed_verified"


def test_scorecard_claims_blocked_when_repo_artifacts_say_sandbox_blocked(tmp_path: Path):
    run_id = "v04pilot_04-bugfix_E_r4"
    files = {
        **base_initial_run_files(run_id, skill_runtime_proof=valid_skill_runtime_proof(run_id)),
        **base_resume_files(run_id, tag="full"),
        **base_resume_files(run_id, tag="stripped"),
        f"benchmark-data/workspaces/{run_id}/repo/VERIFY.md": "sandbox blocked direct execution\n",
        f"benchmark-data/workspaces/{run_id}/repo/HANDOFF.md": "handoff\n",
        f"benchmark-data/workspaces/{run_id}/repo/BUGS.md": "bugs\n",
        f"benchmark-data/resume-workspaces/{run_id}/full/repo/FRESH_SESSION_REVIEW.md": "sandbox blocked direct execution\n",
        f"benchmark-data/resume-workspaces/{run_id}/full/repo/BUGFIX_REVIEW.md": "review\n",
        f"benchmark-data/resume-workspaces/{run_id}/stripped/repo/FRESH_SESSION_REVIEW.md": "review\n",
        f"benchmark-data/resume-workspaces/{run_id}/stripped/repo/BUGFIX_REVIEW.md": "review\n",
        f"benchmark-data/runs/{run_id}/claude_stdout.txt": "I ran VERIFY.sh and pytest -q; both passed.\n",
    }
    bundle = make_bundle(tmp_path, run_id, files)

    row = scorecard.score_bundle(bundle)

    assert row["run_id"] == run_id
    assert row["agent_side_verification_claim"] == "claimed_blocked"
    assert row["skill_runtime_proof_valid"] is True


def test_scorecard_marks_invalid_skill_runtime_proof_as_not_valid(tmp_path: Path):
    run_id = "v04pilot_04-bugfix_E_r5"
    files = {
        **base_initial_run_files(run_id, skill_runtime_proof="proof\n"),
        **base_resume_files(run_id, tag="full"),
        **base_resume_files(run_id, tag="stripped"),
        f"benchmark-data/workspaces/{run_id}/repo/TASK.md": "# task\n",
        f"benchmark-data/workspaces/{run_id}/repo/BUGS.md": "bugs\n",
        f"benchmark-data/workspaces/{run_id}/repo/VERIFY.md": "verify\n",
        f"benchmark-data/workspaces/{run_id}/repo/HANDOFF.md": "handoff\n",
        f"benchmark-data/runs/{run_id}/claude_stdout.txt": "I ran VERIFY.sh and pytest -q; both passed.\n",
        f"benchmark-data/resume-workspaces/{run_id}/stripped/metadata/stripped_artifacts_manifest.json": json.dumps(
            {
                "removed": ["BUGS.md", "VERIFY.md", "HANDOFF.md"],
                "kept_required_outputs": [],
                "skipped": [],
                "ambiguous_not_removed": [],
                "dry_run": False,
            },
            indent=2,
        )
        + "\n",
    }
    bundle = make_bundle(tmp_path, run_id, files)

    row = scorecard.score_bundle(bundle)

    assert row["run_id"] == run_id
    assert row["skill_runtime_proof_present"] is True
    assert row["skill_runtime_proof_valid"] is False


def test_scorecard_handles_initial_fail_bundle_with_no_workflow_artifacts(tmp_path: Path):
    run_id = "v05pilot_05-fake-data_A_r2"
    files = base_initial_fail_run_files(run_id)
    bundle = make_bundle(tmp_path, run_id, files, bundle_type="initial-fail")

    row = scorecard.score_bundle(bundle)

    assert row["run_id"] == run_id
    assert row["bundle_type"] == "initial_fail"
    assert row["initial_ready"] is False
    assert row["failure_stage"] == "initial"
    assert row["failure_reason"] == "missing required blocker themes: denominator inconsistency, leakage or post-treatment field risk"
    assert row["initial_verify_exit"] == 0
    assert row["initial_hidden_exit"] == 1
    assert row["initial_green"] is False
    assert row["full_resume_verify_exit"] == "not_run"
    assert row["full_resume_hidden_exit"] == "not_run"
    assert row["full_resume_green"] is False
    assert row["stripped_resume_verify_exit"] == "not_run"
    assert row["stripped_resume_hidden_exit"] == "not_run"
    assert row["stripped_resume_green"] is False
    assert row["skill_runtime_proof_present"] is False
    assert row["skill_runtime_proof_valid"] is False
    assert row["workflow_artifacts_present"] is False
    assert row["workflow_artifacts"] == ""
    assert row["artifact_mechanism_active"] is False
    assert row["agent_side_verification_claim"] == "claimed_blocked"


def test_scorecard_handles_initial_fail_bundle_with_workflow_artifacts(tmp_path: Path):
    run_id = "v05pilot_05-fake-data_E_r1"
    files = base_initial_fail_run_files(
        run_id,
        skill_runtime_proof=valid_skill_runtime_proof(run_id),
        workflow_artifacts={
            "SPEC.md": "spec\n",
            "VERIFY.md": "sandbox blocked direct execution\n",
            "HANDOFF.md": "handoff\n",
        },
    )
    bundle = make_bundle(tmp_path, run_id, files, bundle_type="initial-fail")

    row = scorecard.score_bundle(bundle)

    assert row["run_id"] == run_id
    assert row["arm_slug"] == "E-ai-engineering-skills"
    assert row["bundle_type"] == "initial_fail"
    assert row["initial_ready"] is False
    assert row["failure_stage"] == "initial"
    assert row["skill_runtime_proof_present"] is True
    assert row["skill_runtime_proof_valid"] is True
    assert row["workflow_artifacts_present"] is True
    assert row["workflow_artifacts"] == "SPEC.md;VERIFY.md;HANDOFF.md;SKILL_RUNTIME_PROOF.md"
    assert row["artifact_mechanism_active"] is False
    assert row["full_resume_verify_exit"] == "not_run"
    assert row["full_resume_hidden_exit"] == "not_run"
    assert row["stripped_resume_verify_exit"] == "not_run"
    assert row["stripped_resume_hidden_exit"] == "not_run"
    assert row["agent_side_verification_claim"] == "claimed_blocked"


def test_hidden_exit_inference_ignores_no_hidden_contract_failed(tmp_path: Path):
    path = tmp_path / "hidden_evaluator_final.txt"
    path.write_text("no hidden contract failed\nHidden Task 4 evaluator passed\n", encoding="utf-8")

    assert scorecard._infer_command_exit([path], "hidden") == 0


def test_scorecard_handles_missing_optional_files_and_writes_outputs(tmp_path: Path, capsys):
    run_id = "v04pilot_04-bugfix_Z_r1"
    files = {
        f"benchmark-data/runs/{run_id}/run_workspace_manifest.json": json.dumps(
            {"dest_repo": f"benchmark-data/workspaces/{run_id}/repo"},
            indent=2,
        )
        + "\n",
        f"benchmark-data/runs/{run_id}/diff.patch": (
            "diff --git a/src/churncalc/metrics.py b/src/churncalc/metrics.py\n"
            "--- a/src/churncalc/metrics.py\n"
            "+++ b/src/churncalc/metrics.py\n"
            "@@\n"
            "-old\n"
            "+new\n"
        ),
        f"benchmark-data/runs/{run_id}/diff_stat.txt": "1 file changed, 1 insertion(+), 1 deletion(-)\n",
        f"benchmark-data/runs/{run_id}/verification_final.txt": (
            "March enterprise churn row:\n"
            "{'month': '2024-03', 'plan': 'enterprise', 'starting_customers': 6, 'cancellations': 5, 'churn_rate': 0.8333333333333334}\n"
            "No impossible churn detected\n"
            "...                                                                      [100%]\n"
            "3 passed in 0.34s\n"
        ),
        f"benchmark-data/runs/{run_id}/claude_stdout.txt": (
            "The sandbox requires interactive approval for all subprocess execution.\n"
        ),
        f"benchmark-data/workspaces/{run_id}/repo/TASK.md": "# task\n",
    }
    bundle = make_bundle(tmp_path, run_id, files)
    csv_out = tmp_path / "scorecards" / "task4_scorecard.csv"
    json_out = tmp_path / "scorecards" / "task4_scorecard.json"

    exit_code = scorecard.main([str(bundle), "--out", str(csv_out), "--json-out", str(json_out)])
    stdout = capsys.readouterr().out

    assert exit_code == 0
    assert "| bundle | run_id | arm_slug |" in stdout
    assert csv_out.exists()
    assert json_out.exists()

    csv_text = csv_out.read_text(encoding="utf-8")
    assert "bundle,run_id,arm_slug" in csv_text

    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[0]["run_id"] == run_id
    assert data[0]["arm_slug"] == "unknown"
    assert data[0]["initial_hidden_exit"] is None
    assert data[0]["skill_runtime_proof_valid"] is False
    assert data[0]["agent_side_verification_claim"] == "claimed_blocked"


def test_scorecard_handles_mixed_eval_and_initial_fail_bundles(tmp_path: Path, capsys):
    eval_run_id = "v04pilot_04-bugfix_A_r1"
    initial_run_id = "v05pilot_05-fake-data_E_r1"
    eval_bundle = make_bundle(
        tmp_path,
        eval_run_id,
        {
            **base_initial_run_files(eval_run_id),
            **base_resume_files(eval_run_id, tag="full"),
            **base_resume_files(eval_run_id, tag="stripped"),
            f"benchmark-data/workspaces/{eval_run_id}/repo/TASK.md": "# task\n",
            f"benchmark-data/resume-workspaces/{eval_run_id}/stripped/metadata/stripped_artifacts_manifest.json": json.dumps(
                {
                    "removed": [],
                    "kept_required_outputs": [],
                    "skipped": [],
                    "ambiguous_not_removed": [],
                    "dry_run": False,
                },
                indent=2,
            )
            + "\n",
        },
    )
    initial_bundle = make_bundle(
        tmp_path,
        initial_run_id,
        base_initial_fail_run_files(
            initial_run_id,
            skill_runtime_proof=valid_skill_runtime_proof(initial_run_id),
            workflow_artifacts={
                "SPEC.md": "spec\n",
                "VERIFY.md": "sandbox blocked direct execution\n",
                "HANDOFF.md": "handoff\n",
            },
        ),
        bundle_type="initial-fail",
    )
    csv_out = tmp_path / "scorecards" / "mixed_scorecard.csv"
    json_out = tmp_path / "scorecards" / "mixed_scorecard.json"

    exit_code = scorecard.main([str(eval_bundle), str(initial_bundle), "--out", str(csv_out), "--json-out", str(json_out)])
    stdout = capsys.readouterr().out

    assert exit_code == 0
    assert "| bundle | run_id | arm_slug |" in stdout
    assert csv_out.exists()
    assert json_out.exists()

    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert [row["bundle_type"] for row in data] == ["eval", "initial_fail"]
    assert data[0]["full_resume_green"] is True
    assert data[1]["full_resume_verify_exit"] == "not_run"
    assert data[0]["skill_runtime_proof_valid"] is False
    assert data[1]["skill_runtime_proof_valid"] is True
