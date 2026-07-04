from __future__ import annotations

import shutil
from pathlib import Path

from benchmark_harness.evaluators import task2_hidden_evaluator as hidden


def _starter_repo(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[2] / "tasks" / "02-channel-normalization" / "starter_repo"
    repo = tmp_path / "repo"
    shutil.copytree(source, repo)
    return repo


def _fix_normalization_bug(repo: Path) -> None:
    metrics = repo / "src" / "acquisition" / "metrics.py"
    text = metrics.read_text(encoding="utf-8")
    text = text.replace(
        '    # BUG: this lowercases labels but leaves whitespace and missing labels unhandled.\n'
        '    result["channel"] = result["channel"].str.lower()\n',
        '    channel = result["channel"].fillna("").astype(str).str.strip().str.lower()\n'
        '    result["channel"] = channel.mask(channel == "", "unknown")\n',
    )
    metrics.write_text(text, encoding="utf-8")


def test_hidden_evaluator_fails_starter_repo(tmp_path: Path):
    repo = _starter_repo(tmp_path)

    errors = hidden.evaluate(repo)

    assert any("email signups expected 2" in error for error in errors)
    assert any("synthetic normalized channels" in error for error in errors)


def test_hidden_evaluator_passes_focused_normalization_fix(tmp_path: Path):
    repo = _starter_repo(tmp_path)
    _fix_normalization_bug(repo)

    assert hidden.evaluate(repo) == []
    assert hidden.main(["--repo", str(repo)]) == 0


def test_hidden_evaluator_rejects_fixture_changes(tmp_path: Path):
    repo = _starter_repo(tmp_path)
    _fix_normalization_bug(repo)
    leads = repo / "fixtures" / "leads.csv"
    leads.write_text(leads.read_text(encoding="utf-8").replace("L002", "L002-edited"), encoding="utf-8")

    errors = hidden.evaluate(repo)

    assert "fixture changed: fixtures/leads.csv" in errors


def test_hidden_evaluator_rejects_fixture_specific_hardcoding(tmp_path: Path):
    repo = _starter_repo(tmp_path)
    _fix_normalization_bug(repo)
    metrics = repo / "src" / "acquisition" / "metrics.py"
    metrics.write_text(metrics.read_text(encoding="utf-8") + "\n# L001 shortcut\n", encoding="utf-8")

    errors = hidden.evaluate(repo)

    assert "metrics.py appears to hardcode fixture-specific results" in errors


def test_hidden_evaluator_reports_missing_source_without_crashing(tmp_path: Path):
    repo = _starter_repo(tmp_path)
    (repo / "src" / "acquisition" / "metrics.py").unlink()

    errors = hidden.evaluate(repo)

    assert any("could not evaluate channel normalization report" in error for error in errors)
