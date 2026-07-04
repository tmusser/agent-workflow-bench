from __future__ import annotations

import json
from pathlib import Path

from benchmark_harness.fresh_session_resume import evaluate_condition, summarize_resume_run, write_summary


def write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_resume_condition(tmp_path: Path, run_id: str, condition: str, *, verify: int | None, hidden: int | None, artifacts: list[str] | None = None) -> None:
    repo = tmp_path / "benchmark-data" / "resume-workspaces" / run_id / condition / "repo"
    out = tmp_path / "benchmark-data" / "resume-runs" / f"{run_id}_{condition}"
    metadata = repo.parent / "metadata" / "resume_workspace_manifest.json"
    repo.mkdir(parents=True)
    out.mkdir(parents=True)
    write(repo / ".git" / "HEAD", "ref: refs/heads/main\n")
    for artifact in artifacts or []:
        write(repo / artifact, f"{artifact}\n")
    if verify is not None:
        write(out / "verification_exit_code.txt", f"{verify}\n")
        write(out / "verification.txt", "verify output\n")
    if hidden is not None:
        write(out / "hidden_evaluator_exit_code.txt", f"{hidden}\n")
        write(out / "hidden_evaluator.txt", "hidden output\n")
    write(out / "diff.patch", "diff --git a/x b/x\n")
    write(out / "git_status.txt", " M src/example.py\n")
    write(out / "FRESH_SESSION_REVIEW.md", "review\n")
    write(metadata, json.dumps({"condition": condition, "condition_undisclosed_to_agent": True}) + "\n")


def test_summarize_resume_run_detects_full_artifact_advantage(tmp_path: Path):
    run_id = "vtest_resume"
    make_resume_condition(tmp_path, run_id, "full", verify=0, hidden=0, artifacts=["HANDOFF.md", "VERIFY.md"])
    make_resume_condition(tmp_path, run_id, "stripped", verify=0, hidden=1, artifacts=[])

    summary = summarize_resume_run(tmp_path, run_id)

    assert summary.schema_version == 1
    assert [condition.condition for condition in summary.conditions] == ["full", "stripped"]
    by_name = {condition.condition: condition for condition in summary.conditions}
    assert by_name["full"].passed is True
    assert by_name["stripped"].passed is False
    assert by_name["full"].review_files == ["FRESH_SESSION_REVIEW.md"]
    assert by_name["full"].workflow_artifacts_present == ["HANDOFF.md", "VERIFY.md"]
    assert summary.comparison["full_vs_stripped"] == {
        "status": "complete",
        "winner": "full",
        "full_passed": True,
        "stripped_passed": False,
        "artifact_advantage_observed": True,
    }


def test_summarize_resume_run_marks_missing_exit_codes_incomplete(tmp_path: Path):
    run_id = "vtest_incomplete"
    make_resume_condition(tmp_path, run_id, "full", verify=0, hidden=0)
    make_resume_condition(tmp_path, run_id, "stripped", verify=None, hidden=None)

    summary = summarize_resume_run(tmp_path, run_id)

    assert summary.comparison["full_vs_stripped"] == {
        "status": "incomplete",
        "reason": "missing_exit_codes",
    }


def test_write_summary_outputs_machine_readable_json(tmp_path: Path):
    run_id = "vtest_write"
    make_resume_condition(tmp_path, run_id, "full", verify=0, hidden=0)
    make_resume_condition(tmp_path, run_id, "stripped", verify=0, hidden=0)
    summary = summarize_resume_run(tmp_path, run_id)

    out = write_summary(summary, tmp_path / "summary.json")
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["run_id"] == run_id
    assert data["comparison"]["full_vs_stripped"]["winner"] == "tie"


def test_evaluate_condition_runs_local_checks_without_llm(tmp_path: Path, monkeypatch):
    run_id = "vtest_evaluate"
    repo = tmp_path / "benchmark-data" / "resume-workspaces" / run_id / "full" / "repo"
    repo.mkdir(parents=True)
    write(repo / ".git" / "HEAD", "ref: refs/heads/main\n")
    verify = repo / "VERIFY.sh"
    write(verify, "#!/usr/bin/env sh\necho verify ok\n")
    verify.chmod(0o755)

    module_root = tmp_path / "evalpkg"
    module_root.mkdir()
    write(module_root / "__init__.py", "")
    write(
        module_root / "dummy_eval.py",
        "from __future__ import annotations\n"
        "import argparse\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('--repo', required=True)\n"
        "    parser.parse_args()\n"
        "    print('hidden ok')\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    condition = evaluate_condition(tmp_path, run_id, "full", "evalpkg.dummy_eval")

    assert condition.verify_exit_code == 0
    assert condition.hidden_evaluator_exit_code == 0
    assert condition.passed is True
    out = tmp_path / "benchmark-data" / "resume-runs" / f"{run_id}_full"
    assert (out / "verification.txt").read_text(encoding="utf-8").strip() == "verify ok"
    assert (out / "hidden_evaluator.txt").read_text(encoding="utf-8").strip() == "hidden ok"
