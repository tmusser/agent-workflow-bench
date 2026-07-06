from __future__ import annotations

from pathlib import Path

from benchmark_harness.render_prompt import render_prompt
from benchmark_harness.task_catalog import resolve_defaults


def test_task7_e_has_ceremony_budget_but_baseline_does_not():
    e_defaults = resolve_defaults("07-dashboard-export-scope-pressure", "E-ai-engineering-skills")
    b_defaults = resolve_defaults("07-dashboard-export-scope-pressure", "B-strong-no-skill")

    assert e_defaults["CEREMONY_BUDGET_DEFAULT"] == "benchmark_harness/protocols/CEREMONY_BUDGET_TASK7.md"
    assert b_defaults["CEREMONY_BUDGET_DEFAULT"] == ""


def test_render_prompt_places_ceremony_budget_before_pressure(tmp_path: Path):
    common = tmp_path / "common.md"
    arm = tmp_path / "arm.md"
    task = tmp_path / "TASK.md"
    budget = tmp_path / "budget.md"
    out = tmp_path / "prompt.md"
    metadata = tmp_path / "pressure.json"

    common.write_text("common wrapper", encoding="utf-8")
    arm.write_text("arm wrapper", encoding="utf-8")
    task.write_text("task body", encoding="utf-8")
    budget.write_text("budget body", encoding="utf-8")

    render_prompt(
        common,
        arm,
        task,
        out,
        pressure_level="high",
        pressure_seed=7,
        context_window_tokens=32000,
        pressure_target_pct=0.50,
        metadata_out=metadata,
        ceremony_budget=budget,
    )

    text = out.read_text(encoding="utf-8")
    assert "# CEREMONY BUDGET" in text
    assert "budget body" in text
    assert text.index("# ARM WRAPPER") < text.index("# CEREMONY BUDGET")
    assert text.index("# CEREMONY BUDGET") < text.index("# SYNTHETIC BACKGROUND CONTEXT")
    assert text.index("# SYNTHETIC BACKGROUND CONTEXT") < text.index("# TASK")


def test_task7_budget_names_budget_controls():
    text = Path("benchmark_harness/protocols/CEREMONY_BUDGET_TASK7.md").read_text(encoding="utf-8")

    assert "Planning budget" in text
    assert "Build budget" in text
    assert "Verification budget" in text
    assert "Diagnostic budget" in text
    assert "Proof reserve" in text
    assert "actual import/call path" in text
    assert "budget ledger" in text
