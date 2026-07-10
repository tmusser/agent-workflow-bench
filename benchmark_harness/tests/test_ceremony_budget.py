from __future__ import annotations

from pathlib import Path

from benchmark_harness.render_prompt import render_prompt
from benchmark_harness.task_catalog import resolve_defaults

ROOT = Path(__file__).resolve().parents[2]


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


def _render_task7_e_prompt(tmp_path: Path, ceremony_budget_env: str | None) -> str:
    defaults = resolve_defaults("07-dashboard-export-scope-pressure", "E-ai-engineering-skills")
    ceremony_budget = (
        ceremony_budget_env
        if ceremony_budget_env is not None
        else defaults["CEREMONY_BUDGET_DEFAULT"]
    )
    out = tmp_path / ("budget_on.md" if ceremony_budget else "budget_off.md")
    render_prompt(
        ROOT / "common_wrapper.md",
        ROOT / defaults["ARM_WRAPPER_DEFAULT"],
        ROOT / defaults["TASK_PROMPT_DEFAULT"],
        out,
        ceremony_budget=ROOT / ceremony_budget if ceremony_budget else None,
    )
    return out.read_text(encoding="utf-8")


def test_task7_e_unset_ceremony_budget_uses_catalog_default(tmp_path: Path):
    prompt = _render_task7_e_prompt(tmp_path, ceremony_budget_env=None)

    assert "# Ceremony Budget — Task 7 E" in prompt


def test_task7_e_empty_ceremony_budget_suppresses_catalog_default(tmp_path: Path):
    prompt = _render_task7_e_prompt(tmp_path, ceremony_budget_env="")

    assert "# Ceremony Budget — Task 7 E" not in prompt


def test_task7_e_budget_section_is_only_prompt_difference(tmp_path: Path):
    budget_on = _render_task7_e_prompt(tmp_path, ceremony_budget_env=None)
    budget_off = _render_task7_e_prompt(tmp_path, ceremony_budget_env="")
    section = (
        "# CEREMONY BUDGET\n\n"
        + (ROOT / "benchmark_harness/protocols/CEREMONY_BUDGET_TASK7.md").read_text(encoding="utf-8").strip()
        + "\n\n"
    )

    assert budget_on.replace(section, "") == budget_off


def test_unrelated_task_arm_prompt_rendering_remains_unchanged(tmp_path: Path):
    defaults = resolve_defaults("01-support-sla-boundary", "C-codex")
    without_budget = tmp_path / "without_budget.md"
    with_default_budget = tmp_path / "with_default_budget.md"

    render_prompt(
        ROOT / "common_wrapper.md",
        ROOT / defaults["ARM_WRAPPER_DEFAULT"],
        ROOT / defaults["TASK_PROMPT_DEFAULT"],
        without_budget,
        ceremony_budget=None,
    )
    render_prompt(
        ROOT / "common_wrapper.md",
        ROOT / defaults["ARM_WRAPPER_DEFAULT"],
        ROOT / defaults["TASK_PROMPT_DEFAULT"],
        with_default_budget,
        ceremony_budget=ROOT / defaults["CEREMONY_BUDGET_DEFAULT"] if defaults["CEREMONY_BUDGET_DEFAULT"] else None,
    )

    assert without_budget.read_text(encoding="utf-8") == with_default_budget.read_text(encoding="utf-8")


def test_smoke_runners_preserve_explicit_empty_ceremony_budget_override():
    legacy = (ROOT / "tools/pilot_smoke_legacy.sh").read_text(encoding="utf-8")
    codex = (ROOT / "tools/pilot_codex_smoke.sh").read_text(encoding="utf-8")

    assert 'CEREMONY_BUDGET="${CEREMONY_BUDGET-$CEREMONY_BUDGET_DEFAULT}"' in legacy
    assert 'CEREMONY_BUDGET="${CEREMONY_BUDGET-$CEREMONY_BUDGET_DEFAULT}"' in codex
    assert '${CEREMONY_BUDGET:+--ceremony-budget "$CEREMONY_BUDGET"}' in legacy
    assert '${CEREMONY_BUDGET:+--ceremony-budget "$CEREMONY_BUDGET"}' in codex
