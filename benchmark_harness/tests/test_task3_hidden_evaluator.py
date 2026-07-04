from __future__ import annotations

import shutil
from pathlib import Path

from benchmark_harness.evaluators import task3_hidden_evaluator as hidden


def _starter_repo(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[2] / "tasks" / "03-refund-grain" / "starter_repo"
    repo = tmp_path / "repo"
    shutil.copytree(source, repo)
    return repo


def _fix_refund_grain_bug(repo: Path) -> None:
    metrics = repo / "src" / "commerce" / "metrics.py"
    text = metrics.read_text(encoding="utf-8")
    text = text.replace(
        '    # BUG: refund rate is order-based, but this counts refund events.\n'
        '    numerators = (\n'
        '        refunds_with_product.groupby("product", sort=True)["refund_id"]\n'
        '        .count()\n'
        '        .reset_index(name="refunded_orders")\n'
        '    )\n',
        '    numerators = (\n'
        '        refunds_with_product.dropna(subset=["product"])\n'
        '        .groupby("product", sort=True)["order_id"]\n'
        '        .nunique()\n'
        '        .reset_index(name="refunded_orders")\n'
        '    )\n',
    )
    metrics.write_text(text, encoding="utf-8")


def test_hidden_evaluator_fails_starter_repo(tmp_path: Path):
    repo = _starter_repo(tmp_path)

    errors = hidden.evaluate(repo)

    assert any("widget refunded_orders expected 1" in error for error in errors)
    assert any("synthetic alpha refunded_orders expected 1" in error for error in errors)


def test_hidden_evaluator_passes_focused_refund_grain_fix(tmp_path: Path):
    repo = _starter_repo(tmp_path)
    _fix_refund_grain_bug(repo)

    assert hidden.evaluate(repo) == []
    assert hidden.main(["--repo", str(repo)]) == 0


def test_hidden_evaluator_rejects_fixture_changes(tmp_path: Path):
    repo = _starter_repo(tmp_path)
    _fix_refund_grain_bug(repo)
    refunds = repo / "fixtures" / "refund_events.csv"
    refunds.write_text(refunds.read_text(encoding="utf-8").replace("R002", "R002-edited"), encoding="utf-8")

    errors = hidden.evaluate(repo)

    assert "fixture changed: fixtures/refund_events.csv" in errors


def test_hidden_evaluator_rejects_fixture_specific_hardcoding(tmp_path: Path):
    repo = _starter_repo(tmp_path)
    _fix_refund_grain_bug(repo)
    metrics = repo / "src" / "commerce" / "metrics.py"
    metrics.write_text(metrics.read_text(encoding="utf-8") + "\n# O001 shortcut\n", encoding="utf-8")

    errors = hidden.evaluate(repo)

    assert "metrics.py appears to hardcode fixture-specific results" in errors


def test_hidden_evaluator_rejects_rate_clamping(tmp_path: Path):
    repo = _starter_repo(tmp_path)
    _fix_refund_grain_bug(repo)
    metrics = repo / "src" / "commerce" / "metrics.py"
    metrics.write_text(metrics.read_text(encoding="utf-8") + "\n# clip(1.0) would be a shortcut\n", encoding="utf-8")

    errors = hidden.evaluate(repo)

    assert "metrics.py appears to clamp refund rates instead of fixing the order grain" in errors


def test_hidden_evaluator_reports_missing_source_without_crashing(tmp_path: Path):
    repo = _starter_repo(tmp_path)
    (repo / "src" / "commerce" / "metrics.py").unlink()

    errors = hidden.evaluate(repo)

    assert any("could not evaluate refund grain report" in error for error in errors)
