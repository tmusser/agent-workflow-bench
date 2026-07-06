from __future__ import annotations

from pathlib import Path

from benchmark_harness.task_catalog import resolve_defaults, resolve_task_config


def test_task1_defaults_are_cataloged():
    defaults = resolve_defaults("01-support-sla-boundary", "E-ai-engineering-skills")

    assert defaults["TASK_ID_DEFAULT"] == "01-sla-boundary"
    assert defaults["TASK_NAME_DEFAULT"] == "Support SLA Boundary Regression"
    assert defaults["STARTER_DEFAULT"] == "tasks/01-support-sla-boundary/starter_repo"
    assert defaults["TASK_PROMPT_DEFAULT"] == "tasks/01-support-sla-boundary/starter_repo/TASK.md"
    assert defaults["MANIFEST_DEFAULT"] == "tasks/01-support-sla-boundary/task_output_manifest.yml"
    assert defaults["HIDDEN_EVALUATOR_MODULE_DEFAULT"] == "benchmark_harness.evaluators.task1_hidden_evaluator"
    assert defaults["RUN_PREFIX_DEFAULT"] == "v01pilot_01-sla-boundary"
    assert defaults["ARM_WRAPPER_DEFAULT"] == "arms/E-ai-engineering-skills.md"
    assert defaults["EXPECTED_STARTER_VERIFY_FAILURE_DEFAULT"] == "true"


def test_task4_defaults_keep_existing_wrapper():
    defaults = resolve_defaults("04-impossible-churn", "E-ai-engineering-skills")

    assert defaults["TASK_ID_DEFAULT"] == "04-bugfix"
    assert defaults["HIDDEN_EVALUATOR_MODULE_DEFAULT"] == "benchmark_harness.evaluators.task4_hidden_evaluator"
    assert defaults["ARM_WRAPPER_DEFAULT"] == "arms/E-ai-engineering-skills.md"
    assert defaults["EXPECTED_STARTER_VERIFY_FAILURE_DEFAULT"] == "true"


def test_task5_defaults_switch_to_task_specific_e_wrapper():
    defaults = resolve_defaults("05-fake-data-analysis", "E-ai-engineering-skills")

    assert defaults["TASK_ID_DEFAULT"] == "05-fake-data"
    assert defaults["HIDDEN_EVALUATOR_MODULE_DEFAULT"] == "benchmark_harness.evaluators.task5_hidden_evaluator"
    assert defaults["ARM_WRAPPER_DEFAULT"] == "arms/E-ai-engineering-skills-task5.md"
    assert defaults["EXPECTED_STARTER_VERIFY_FAILURE_DEFAULT"] == "false"


def test_task6_defaults_use_task_specific_wrappers():
    defaults_b = resolve_defaults("06-activation-metric-migration", "B-strong-no-skill")
    defaults_e = resolve_defaults("06-activation-metric-migration", "E-ai-engineering-skills")

    assert defaults_b["TASK_ID_DEFAULT"] == "06-activation"
    assert defaults_b["HIDDEN_EVALUATOR_MODULE_DEFAULT"] == "benchmark_harness.evaluators.task6_hidden_evaluator"
    assert defaults_b["ARM_WRAPPER_DEFAULT"] == "arms/B-strong-no-skill-task6.md"
    assert defaults_b["EXPECTED_STARTER_VERIFY_FAILURE_DEFAULT"] == "true"
    assert defaults_e["ARM_WRAPPER_DEFAULT"] == "arms/E-ai-engineering-skills-task6.md"


def test_task7_defaults_use_task_specific_wrappers_and_resume_prompt():
    defaults_baseline = resolve_defaults("07-dashboard-export-scope-pressure", "B-baseline")
    defaults_b = resolve_defaults("07-dashboard-export-scope-pressure", "B-strong-no-skill")
    defaults_e = resolve_defaults("07-dashboard-export-scope-pressure", "E-ai-engineering-skills")

    assert defaults_b["TASK_ID_DEFAULT"] == "07-dashboard-export"
    assert defaults_b["TASK_NAME_DEFAULT"] == "Finance Weekly CSV Export"
    assert defaults_b["STARTER_DEFAULT"] == "tasks/07-dashboard-export-scope-pressure/starter_repo"
    assert defaults_b["TASK_PROMPT_DEFAULT"] == "tasks/07-dashboard-export-scope-pressure/starter_repo/TASK.md"
    assert defaults_b["MANIFEST_DEFAULT"] == "tasks/07-dashboard-export-scope-pressure/task_output_manifest.yml"
    assert defaults_b["HIDDEN_EVALUATOR_MODULE_DEFAULT"] == "benchmark_harness.evaluators.task7_hidden_evaluator"
    assert defaults_b["RESUME_HIDDEN_EVALUATOR_MODULE_DEFAULT"] == "benchmark_harness.evaluators.task7_resume_evaluator"
    assert defaults_b["FRESH_SESSION_PROMPT_DEFAULT"] == "benchmark_harness/protocols/FRESH_SESSION_PROMPT_TASK7.md"
    assert defaults_b["RUN_PREFIX_DEFAULT"] == "v07pilot_07-dashboard-export"
    assert defaults_b["ARM_WRAPPER_DEFAULT"] == "arms/B-strong-no-skill-task7.md"
    assert defaults_b["EXPECTED_STARTER_VERIFY_FAILURE_DEFAULT"] == "true"
    assert defaults_baseline["ARM_WRAPPER_DEFAULT"] == "arms/B-strong-no-skill-task7.md"
    assert defaults_e["ARM_WRAPPER_DEFAULT"] == "arms/E-ai-engineering-skills-task7.md"


def test_task7_e_wrapper_mentions_strict_runtime_proof_template():
    wrapper = Path(__file__).resolve().parents[2] / "arms" / "E-ai-engineering-skills-task7.md"
    text = wrapper.read_text(encoding="utf-8")

    assert ".benchmark/SKILL_RUNTIME_CONTEXT.md" in text
    assert "validate_skill_runtime_proof" in text
    assert "Pinned commit SHA" in text
    assert "Activation mechanism" in text
    assert "SPEC.md" in text
    assert "VERIFY.md" in text
    assert "HANDOFF.md" in text
    assert "SKILL_RUNTIME_PROOF.md" in text
    assert "During-run evidence" in text
    assert "keep" in text
    assert "single success word" in text
    assert "Pre-run availability check" in text


def test_task6_e_wrapper_mentions_strict_runtime_proof_template():
    wrapper = Path(__file__).resolve().parents[2] / "arms" / "E-ai-engineering-skills-task6.md"
    text = wrapper.read_text(encoding="utf-8")

    assert ".benchmark/SKILL_RUNTIME_CONTEXT.md" in text
    assert "validate_skill_runtime_proof" in text
    assert "Pinned commit SHA" in text
    assert "Activation mechanism" in text
    assert "SPEC.md" in text
    assert "VERIFY.md" in text
    assert "HANDOFF.md" in text
    assert "SKILL_RUNTIME_PROOF.md" in text
    assert "During-run evidence" in text


def test_task6_manifest_strips_implementation_note_and_skill_proof():
    manifest = Path(__file__).resolve().parents[2] / "tasks" / "06-activation-metric-migration" / "task_output_manifest.yml"
    text = manifest.read_text(encoding="utf-8")

    assert "IMPLEMENTATION_NOTE.md" in text
    assert "IMPLEMENTATION_NOTES.md" in text
    assert "implementation_note.md" in text
    assert "implementation_notes.md" in text
    assert "SKILL_RUNTIME_PROOF.md" in text
    assert "skill_runtime_proof.md" in text


def test_task6_fresh_session_prompt_is_task_specific():
    prompt = Path(__file__).resolve().parents[2] / "benchmark_harness" / "protocols" / "FRESH_SESSION_PROMPT_TASK6.md"
    text = prompt.read_text(encoding="utf-8")

    assert "activation_v1_v2_comparison.csv" in text
    assert "January and February" in text
    assert "FRESH_SESSION_REVIEW.md" in text
    assert "Task 4" not in text
    assert "BUGFIX_REVIEW.md" not in text


def test_pilot_smoke_entrypoint_resolves_python_before_legacy_helper():
    root = Path(__file__).resolve().parents[2]
    entrypoint = (root / "tools" / "pilot_smoke.sh").read_text(encoding="utf-8")
    legacy = (root / "tools" / "pilot_smoke_legacy.sh").read_text(encoding="utf-8")

    assert "resolve_python()" in entrypoint
    assert "python3.11" in entrypoint
    assert "pilot_smoke_legacy.sh" in entrypoint
    assert "SHIM_DIR:$PATH" in entrypoint

    assert 'FRESH_PROMPT="${FRESH_SESSION_PROMPT:-$FRESH_SESSION_PROMPT_DEFAULT}"' in legacy
    assert 'RESUME_HIDDEN_EVALUATOR_MODULE="${RESUME_HIDDEN_EVALUATOR_MODULE:-$RESUME_HIDDEN_EVALUATOR_MODULE_DEFAULT}"' in legacy
    assert "CLAUDE_OUTPUT_FORMAT=json" in legacy
    assert 'if [[ "${CLAUDE_OUTPUT_FORMAT:-}" != "json" ]] && claude_supports_stream_json;' in legacy
    assert "stream-json / stream_json observation" in legacy
    assert "forces JSON output and mtime_polling observation" in legacy
    assert "PRESSURE_LEVEL" in legacy
    assert "--pressure-level" in legacy
    assert "context_pressure.json" in legacy
    assert "ENABLE_SKILL_RUNTIME_FINALIZER" in legacy
    assert "benchmark_harness.skill_runtime_finalizer" in legacy
    assert "SKILL_RUNTIME_FINALIZER_PROMPT.md" in legacy
    assert "run_metrics.json" in legacy
    assert 'if [[ "$ARM_SLUG" == E-* ]]; then' in legacy
    assert 'Non-baseline arm did not produce SKILL_RUNTIME_PROOF.md.' not in legacy


def test_task7_fresh_session_prompt_is_task_specific():
    prompt = Path(__file__).resolve().parents[2] / "benchmark_harness" / "protocols" / "FRESH_SESSION_PROMPT_TASK7.md"
    text = prompt.read_text(encoding="utf-8")

    assert "region filter" in text
    assert "finance_weekly" in text
    assert "Do not build a generic filtering framework." in text
    assert "First run `./VERIFY.sh`" in text
    assert "If it exits 0, stop immediately." in text
    assert text.index("First run `./VERIFY.sh`") < text.index("If it fails, inspect any durable implementation")
    assert "missing `SPEC.md`, `VERIFY.md`, `SKILL_RUNTIME_PROOF.md`" in text
    assert "If `./VERIFY.sh` fails, diagnose the failure and only then edit source files." in text
    assert "Do not edit source files just to recreate missing workflow artifacts." in text
    assert "Task 4" not in text


def test_unknown_task_slug_is_rejected():
    try:
        resolve_task_config("does-not-exist")
    except KeyError as exc:
        assert "unknown task slug" in str(exc)
    else:  # pragma: no cover - defensive guard
        raise AssertionError("expected unknown task slug to raise")
