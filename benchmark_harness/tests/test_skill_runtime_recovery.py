from __future__ import annotations

import json
import textwrap
from pathlib import Path

from benchmark_harness import skill_runtime_recovery


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def valid_skill_runtime_proof(run_id: str) -> str:
    return textwrap.dedent(
        f"""\
        # Skill Runtime Proof

        ## Run
        - Run ID: {run_id}
        - Arm: E-ai-engineering-skills
        - Task: 04-impossible-churn - Impossible Churn Regression
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
        - Environment variables relevant to skill loading: CLAUDE_PLUGIN_DIR=/tmp/skills/repo

        ## Pre-run availability check
        - Command run: test -f ~/.claude/skills/repo/README.md
        - Result: available
        - Evidence path: benchmark-data/runs/{run_id}/skill_available.txt

        ## During-run evidence
        - Invocation evidence level: agent_declared
        - Did the agent mention or invoke the skill? yes
        - Evidence: benchmark-data/runs/{run_id}/stdout.txt
        - Notes: none

        ## Post-run caveat
        - Could a bad result be due to the skill not being loaded? no
        - Reviewer notes: none
        """
    )


def valid_skill_runtime_context(run_root: Path) -> str:
    return textwrap.dedent(
        f"""\
        # Skill Runtime Context

        - Repo URL: https://example.com/repo.git
        - Pinned commit SHA: 0123456789abcdef0123456789abcdef01234567
        - Local plugin path: /tmp/skills/repo
        - Agent-visible plugin path: /tmp/skills/repo
        - Pin command: ./benchmark_harness/scripts/pin_skill_repos.sh local_plugins
        - Pre-run availability check command: test -f /tmp/skills/repo/PINNED_SKILL_REPO.md
        - Pre-run availability check result: available
        - Pre-run availability evidence path: {run_root / ".benchmark" / "SKILL_RUNTIME_CONTEXT.md"}
        - Task slug: 04-impossible-churn
        - Arm slug: E-ai-engineering-skills
        - Run ID: r1
        """
    )


def base_prompt() -> str:
    return textwrap.dedent(
        """\
        # ARM WRAPPER

        Create `SKILL_RUNTIME_PROOF.md` even if verification still fails.
        """
    )


def make_run(
    tmp_path: Path,
    run_id: str,
    *,
    phase: str = "initial",
    prompt_text: str | None = None,
    proof_text: str | None = None,
    context_text: str | None = None,
    verification_text: str = "3 passed in 0.34s\n",
    hidden_text: str = "Hidden Task 4 evaluator passed\n",
    diff_text: str = (
        "diff --git a/src/churncalc/metrics.py b/src/churncalc/metrics.py\n"
        "--- a/src/churncalc/metrics.py\n"
        "+++ b/src/churncalc/metrics.py\n"
        "@@\n"
        "-old\n"
        "+new\n"
    ),
    collect_exit_code: int = 0,
    codex_exit_code: int = 0,
    stdout_text: str = '{"message":"ok"}\n',
    stderr_text: str = "",
    reached_max_turns: str | bool = False,
    task_slug: str = "04-impossible-churn",
) -> tuple[Path, Path, Path]:
    root = tmp_path / run_id
    run_dir = root / "benchmark-data" / "runs" / run_id
    workspace = root / "benchmark-data" / "workspaces" / run_id / "repo"
    prompt_path = run_dir / "prompt.md"

    write(
        run_dir / "run_provenance.json",
        json.dumps(
            {
                "task_slug": task_slug,
                "model": "gpt-5.4-mini",
                "effort": "metadata-only",
                "max_turns": 20,
                "permission_mode": "workspace-write",
                "output_format": "json",
                "label": phase,
            },
            indent=2,
        )
        + "\n",
    )
    write(
        run_dir / "run_metrics.json",
        json.dumps(
            {
                "run_id": run_id,
                "task_slug": task_slug,
                "arm_slug": "E-ai-engineering-skills",
                "runner_exit_code": codex_exit_code,
                "agent_exit_code": codex_exit_code,
                "output_format": "json",
                "reached_max_turns": reached_max_turns,
                "stdout_bytes": len(stdout_text.encode("utf-8")),
                "stderr_bytes": len(stderr_text.encode("utf-8")),
            },
            indent=2,
        )
        + "\n",
    )
    write(run_dir / "codex_stdout.txt", stdout_text)
    write(run_dir / "codex_stderr.txt", stderr_text)
    write(run_dir / "codex_exit_code.txt", f"{codex_exit_code}\n")
    write(run_dir / "verification_final.txt" if phase == "initial" else run_dir / "verification.txt", verification_text)
    write(run_dir / "hidden_evaluator_final.txt" if phase == "initial" else run_dir / "hidden_evaluator.txt", hidden_text)
    write(run_dir / "diff.patch", diff_text)
    write(run_dir / "diff_stat.txt", "1 file changed, 1 insertion(+), 1 deletion(-)\n" if diff_text else "0 files changed\n")
    write(prompt_path, prompt_text or base_prompt())

    if context_text is not None:
        write(workspace / ".benchmark" / "SKILL_RUNTIME_CONTEXT.md", context_text)
    if proof_text is not None:
        write(workspace / "SKILL_RUNTIME_PROOF.md", proof_text)

    return root, run_dir, workspace


def test_recovery_marks_success_with_required_artifacts_and_is_metadata_only(tmp_path: Path):
    _, run_dir, workspace = make_run(
        tmp_path,
        "r1",
        prompt_text=base_prompt(),
        proof_text=valid_skill_runtime_proof("r1"),
        context_text=valid_skill_runtime_context(tmp_path / "r1" / "benchmark-data" / "runs" / "r1"),
        stdout_text='{"message":"SECRET_PROMPT_BODY"}\n',
    )

    recovery = skill_runtime_recovery.build_skill_runtime_recovery(
        run_dir=run_dir,
        workspace_root=workspace,
        prompt_file=run_dir / "prompt.md",
        run_id="r1",
        task_slug="04-impossible-churn",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        collect_exit_code=0,
    )

    assert recovery["classification"] == "completed_with_required_artifacts"
    assert recovery["public_status"] == "passed"
    assert recovery["failure_category"] is None
    assert recovery["skill_runtime_proof_present"] is True
    assert recovery["skill_runtime_proof_valid"] is True
    assert recovery["skill_runtime_context_present"] is True
    assert recovery["prompt_explicit"] is True
    assert recovery["stop_after_initial"] is False
    assert recovery["changed_files"] == ["src/churncalc/metrics.py"]
    assert recovery["workflow_artifacts"] == ["SKILL_RUNTIME_PROOF.md"]

    written = json.loads((run_dir / "skill_runtime_recovery.json").read_text(encoding="utf-8"))
    assert written["classification"] == "completed_with_required_artifacts"
    text = (run_dir / "skill_runtime_recovery.md").read_text(encoding="utf-8")
    assert "SECRET_PROMPT_BODY" not in json.dumps(written)
    assert "SECRET_PROMPT_BODY" not in text


def test_recovery_marks_missing_proof_after_attempt_as_artifact_contract_failure(tmp_path: Path):
    _, run_dir, workspace = make_run(
        tmp_path,
        "r2",
        prompt_text=base_prompt(),
        context_text=valid_skill_runtime_context(tmp_path / "r2" / "benchmark-data" / "runs" / "r2"),
        proof_text=None,
        verification_text="3 passed in 0.34s\n",
        hidden_text="Hidden Task 4 evaluator passed\n",
        diff_text=(
            "diff --git a/tests/test_impossible_churn_bug.py b/tests/test_impossible_churn_bug.py\n"
            "--- a/tests/test_impossible_churn_bug.py\n"
            "+++ b/tests/test_impossible_churn_bug.py\n"
            "@@\n"
            "+def test_active_interval_mapping():\n"
            "+    assert cancellation_count == 1\n"
        ),
        collect_exit_code=1,
        stdout_text='{"message":"worked"}\n',
    )

    recovery = skill_runtime_recovery.build_skill_runtime_recovery(
        run_dir=run_dir,
        workspace_root=workspace,
        prompt_file=run_dir / "prompt.md",
        run_id="r2",
        task_slug="04-impossible-churn",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        collect_exit_code=1,
    )

    assert recovery["classification"] == "missing_skill_runtime_proof"
    assert recovery["public_status"] == "failed: missing proof after task attempt"
    assert recovery["failure_category"] == "artifact_contract_failure"
    assert recovery["skill_runtime_proof_present"] is False
    assert recovery["skill_runtime_proof_valid"] is False
    assert recovery["skill_runtime_context_present"] is True
    assert recovery["stop_after_initial"] is False
    assert recovery["functional_green"] is True


def test_recovery_marks_usage_limit_blocked_before_attempt(tmp_path: Path):
    _, run_dir, workspace = make_run(
        tmp_path,
        "r3",
        prompt_text=base_prompt(),
        context_text=valid_skill_runtime_context(tmp_path / "r3" / "benchmark-data" / "runs" / "r3"),
        proof_text=None,
        diff_text="",
        verification_text="3 passed in 0.34s\n",
        hidden_text="Hidden Task 4 evaluator passed\n",
        collect_exit_code=1,
        stdout_text='{"message":"Agent stopped because it reached max turns"}\n',
        reached_max_turns=True,
    )

    recovery = skill_runtime_recovery.build_skill_runtime_recovery(
        run_dir=run_dir,
        workspace_root=workspace,
        prompt_file=run_dir / "prompt.md",
        run_id="r3",
        task_slug="04-impossible-churn",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        collect_exit_code=1,
    )

    assert recovery["classification"] == "usage_limit_blocked_before_attempt"
    assert recovery["public_status"] == "blocked: usage limit before task attempt"
    assert recovery["failure_category"] == "environment_failure"
    assert recovery["reached_max_turns"] is True
    assert recovery["stop_after_initial"] is True
    assert recovery["task_attempted"] is False


def test_recovery_marks_environment_or_context_blockers(tmp_path: Path):
    _, run_dir, workspace = make_run(
        tmp_path,
        "r4",
        prompt_text=base_prompt(),
        context_text=None,
        proof_text=None,
        diff_text="",
        verification_text="3 passed in 0.34s\n",
        hidden_text="Hidden Task 4 evaluator passed\n",
        collect_exit_code=1,
        stderr_text="ERROR: command not found: codex\n",
    )

    recovery = skill_runtime_recovery.build_skill_runtime_recovery(
        run_dir=run_dir,
        workspace_root=workspace,
        prompt_file=run_dir / "prompt.md",
        run_id="r4",
        task_slug="04-impossible-churn",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        collect_exit_code=1,
    )

    assert recovery["classification"] == "environment_blocked_before_attempt"
    assert recovery["public_status"] == "blocked: environment before task attempt"
    assert recovery["failure_category"] == "environment_failure"
    assert recovery["skill_runtime_context_present"] is False
    assert recovery["stop_after_initial"] is True
    assert recovery["task_attempted"] is False
