from __future__ import annotations

from benchmark_harness.evaluators import task7_resume_evaluator as resume
from benchmark_harness.tests.test_task7_hidden_evaluator import _make_correct_repo


def test_resume_evaluator_cli_passes_correct_repo(tmp_path):
    repo = _make_correct_repo(tmp_path)

    result = resume.evaluate(repo)

    assert result["phase"] == "resume"
    assert result["overall_green"] is True
    assert result["resume_functional_green"] is True
    assert result["resume_scope_green"] is True
    assert result["resume_region_filter_green"] is True
    assert result["resume_no_match_behavior_preserved"] is True
    assert result["resume_small_diff_green"] is True
    assert resume.main(["--repo", str(repo)]) == 0
