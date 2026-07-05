from __future__ import annotations

import importlib
import shutil
import sys
import textwrap
from pathlib import Path

import pandas as pd

from benchmark_harness.evaluators.task6_resume_evaluator import evaluate, main as resume_main
from benchmark_harness.tests.test_task6_hidden_evaluator import CORRECT_ACTIVATION_SOURCE, STARTER

PUBLIC_COMPARISON_ROWS = [
    {
        "month": "2026-01",
        "v1_eligible_users": 3,
        "v1_activated_users": 2,
        "v1_activation_rate": 0.666667,
        "v2_eligible_users": 3,
        "v2_activated_users": 2,
        "v2_activation_rate": 0.666667,
    },
    {
        "month": "2026-02",
        "v1_eligible_users": 2,
        "v1_activated_users": 1,
        "v1_activation_rate": 0.5,
        "v2_eligible_users": 2,
        "v2_activated_users": 1,
        "v2_activation_rate": 0.5,
    },
]

COMPARISON_SCRIPT = textwrap.dedent(
    """
    from __future__ import annotations

    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    SRC = ROOT / "src"
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))

    import pandas as pd
    from activation_metrics.activation import compute_activation_rate_v1, compute_activation_rate_v2
    from activation_metrics.load import load_events, load_users


    def main() -> int:
        users = load_users(ROOT / "fixtures")
        events = load_events(ROOT / "fixtures")
        rows = []
        for month in ["2026-01", "2026-02"]:
            v1 = compute_activation_rate_v1(users, events, month)
            v2 = compute_activation_rate_v2(users, events, month)
            rows.append(
                {
                    "month": month,
                    "v1_eligible_users": v1["eligible_users"],
                    "v1_activated_users": v1["activated_users"],
                    "v1_activation_rate": v1["activation_rate"],
                    "v2_eligible_users": v2["eligible_users"],
                    "v2_activated_users": v2["activated_users"],
                    "v2_activation_rate": v2["activation_rate"],
                }
            )

        out_path = ROOT / "outputs" / "activation_v1_v2_comparison.csv"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out_path, index=False)
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    """
)


def _copy_starter(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(
        STARTER,
        repo,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "outputs"),
    )
    return repo


def _write_activation_module(repo: Path, source: str) -> None:
    (repo / "src" / "activation_metrics" / "activation.py").write_text(source, encoding="utf-8")
    importlib.invalidate_caches()


def _write_review(repo: Path, text: str = "# Fresh Session Review\nresume evidence\n") -> None:
    (repo / "FRESH_SESSION_REVIEW.md").write_text(text, encoding="utf-8")


def _write_comparison_script(repo: Path) -> Path:
    script = repo / "scripts" / "generate_v1_v2_comparison.py"
    script.write_text(COMPARISON_SCRIPT, encoding="utf-8")
    importlib.invalidate_caches()
    return script


def _write_valid_public_csv(repo: Path) -> None:
    out_path = repo / "outputs" / "activation_v1_v2_comparison.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(PUBLIC_COMPARISON_ROWS).to_csv(out_path, index=False)


def _make_valid_repo(tmp_path: Path, *, include_csv: bool = True, include_review: bool = True) -> Path:
    repo = _copy_starter(tmp_path)
    _write_activation_module(repo, CORRECT_ACTIVATION_SOURCE)
    _write_comparison_script(repo)
    if include_csv:
        _write_comparison_script(repo)
        import subprocess
        subprocess.run(
            [
                sys.executable,
                "scripts/generate_v1_v2_comparison.py",
            ],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
    if include_review:
        _write_review(repo)
    return repo


def test_resume_evaluator_passes_valid_complete_repo(tmp_path: Path):
    repo = _make_valid_repo(tmp_path)

    result = evaluate(repo)

    assert result["hidden_contract_pass"] is True
    assert result["fresh_review_present"] is True
    assert result["comparison_csv_present"] is True
    assert result["comparison_csv_valid"] is True
    assert result["comparison_script_present"] is True
    assert result["comparison_script_generates_valid_csv"] is True
    assert result["resume_request_complete"] is True
    assert result["latent_resume_solution_present"] is True
    assert result["errors"] == []
    assert resume_main(["--repo", str(repo)]) == 0


def test_resume_evaluator_reports_latent_solution_without_csv(tmp_path: Path):
    repo = _make_valid_repo(tmp_path, include_csv=False)

    result = evaluate(repo)

    assert result["hidden_contract_pass"] is True
    assert result["fresh_review_present"] is True
    assert result["comparison_csv_present"] is False
    assert result["comparison_csv_valid"] is False
    assert result["comparison_script_present"] is True
    assert result["comparison_script_generates_valid_csv"] is True
    assert result["resume_request_complete"] is False
    assert result["latent_resume_solution_present"] is True
    assert resume_main(["--repo", str(repo)]) != 0


def test_resume_evaluator_rejects_bad_csv_schema(tmp_path: Path):
    repo = _make_valid_repo(tmp_path, include_csv=False)
    bad = repo / "outputs" / "activation_v1_v2_comparison.csv"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("month,eligible_users\n2026-01,3\n", encoding="utf-8")

    result = evaluate(repo)

    assert result["comparison_csv_present"] is True
    assert result["comparison_csv_valid"] is False
    assert result["resume_request_complete"] is False
    assert resume_main(["--repo", str(repo)]) != 0


def test_resume_evaluator_rejects_wrong_csv_values(tmp_path: Path):
    repo = _make_valid_repo(tmp_path, include_csv=False)
    bad = repo / "outputs" / "activation_v1_v2_comparison.csv"
    bad.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "month": "2026-01",
                "v1_eligible_users": 99,
                "v1_activated_users": 98,
                "v1_activation_rate": 0.99,
                "v2_eligible_users": 99,
                "v2_activated_users": 98,
                "v2_activation_rate": 0.99,
            }
        ]
    ).to_csv(bad, index=False)

    result = evaluate(repo)

    assert result["comparison_csv_present"] is True
    assert result["comparison_csv_valid"] is False
    assert result["resume_request_complete"] is False
    assert resume_main(["--repo", str(repo)]) != 0


def test_resume_evaluator_rejects_missing_review(tmp_path: Path):
    repo = _make_valid_repo(tmp_path, include_review=False)

    result = evaluate(repo)

    assert result["hidden_contract_pass"] is True
    assert result["fresh_review_present"] is False
    assert result["resume_request_complete"] is True
    assert resume_main(["--repo", str(repo)]) != 0


def test_resume_evaluator_rejects_hidden_failure(tmp_path: Path):
    repo = _make_valid_repo(tmp_path)
    _write_activation_module(
        repo,
        CORRECT_ACTIVATION_SOURCE.replace(
            "def compute_activation_rate_v2(users: pd.DataFrame, events: pd.DataFrame, month: str) -> dict[str, object]:\n",
            "def compute_activation_rate_v2(users: pd.DataFrame, events: pd.DataFrame, month: str) -> dict[str, object]:\n        raise NotImplementedError('broken on purpose')\n",
            1,
        ),
    )

    result = evaluate(repo)

    assert result["hidden_contract_pass"] is False
    assert result["resume_request_complete"] is True
    assert resume_main(["--repo", str(repo)]) != 0
