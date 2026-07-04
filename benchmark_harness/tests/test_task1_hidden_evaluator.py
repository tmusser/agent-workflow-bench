from __future__ import annotations

import shutil
from pathlib import Path

from benchmark_harness.evaluators import task1_hidden_evaluator as hidden


def _starter_repo(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[2] / "tasks" / "01-support-sla-boundary" / "starter_repo"
    repo = tmp_path / "repo"
    shutil.copytree(source, repo)
    return repo


def _fix_boundary_bug(repo: Path) -> None:
    metrics = repo / "src" / "supportops" / "metrics.py"
    text = metrics.read_text(encoding="utf-8")
    text = text.replace(
        'result["sla_breached"] = result["response_hours"] >= result["sla_hours"]',
        'result["sla_breached"] = result["response_hours"] > result["sla_hours"]',
    )
    metrics.write_text(text, encoding="utf-8")


def test_hidden_evaluator_fails_starter_repo(tmp_path: Path):
    repo = _starter_repo(tmp_path)

    errors = hidden.evaluate(repo)

    assert any("breached_tickets expected 1" in error for error in errors)
    assert any("SYN-urgent-exact" in error for error in errors)


def test_hidden_evaluator_passes_focused_boundary_fix(tmp_path: Path):
    repo = _starter_repo(tmp_path)
    _fix_boundary_bug(repo)

    assert hidden.evaluate(repo) == []
    assert hidden.main(["--repo", str(repo)]) == 0


def test_hidden_evaluator_rejects_fixture_changes(tmp_path: Path):
    repo = _starter_repo(tmp_path)
    _fix_boundary_bug(repo)
    tickets = repo / "fixtures" / "tickets.csv"
    tickets.write_text(tickets.read_text(encoding="utf-8").replace("T002", "T002-edited"), encoding="utf-8")

    errors = hidden.evaluate(repo)

    assert "fixture changed: fixtures/tickets.csv" in errors


def test_hidden_evaluator_rejects_fixture_specific_hardcoding(tmp_path: Path):
    repo = _starter_repo(tmp_path)
    _fix_boundary_bug(repo)
    metrics = repo / "src" / "supportops" / "metrics.py"
    metrics.write_text(metrics.read_text(encoding="utf-8") + "\n# T001 shortcut\n", encoding="utf-8")

    errors = hidden.evaluate(repo)

    assert "metrics.py appears to hardcode fixture-specific results" in errors
