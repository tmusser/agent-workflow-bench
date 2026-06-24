from __future__ import annotations

from benchmark_harness.task_catalog import resolve_defaults, resolve_task_config


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


def test_unknown_task_slug_is_rejected():
    try:
        resolve_task_config("does-not-exist")
    except KeyError as exc:
        assert "unknown task slug" in str(exc)
    else:  # pragma: no cover - defensive guard
        raise AssertionError("expected unknown task slug to raise")
