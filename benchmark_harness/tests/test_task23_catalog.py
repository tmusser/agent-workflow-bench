from __future__ import annotations

from benchmark_harness.task_catalog import resolve_defaults


def test_task2_defaults_are_cataloged():
    defaults = resolve_defaults("02-channel-normalization", "E-ai-engineering-skills")

    assert defaults["TASK_ID_DEFAULT"] == "02-channel-normalization"
    assert defaults["TASK_NAME_DEFAULT"] == "Campaign Channel Normalization"
    assert defaults["STARTER_DEFAULT"] == "tasks/02-channel-normalization/starter_repo"
    assert defaults["TASK_PROMPT_DEFAULT"] == "tasks/02-channel-normalization/starter_repo/TASK.md"
    assert defaults["MANIFEST_DEFAULT"] == "tasks/02-channel-normalization/task_output_manifest.yml"
    assert defaults["HIDDEN_EVALUATOR_MODULE_DEFAULT"] == "benchmark_harness.evaluators.task2_hidden_evaluator"
    assert defaults["RUN_PREFIX_DEFAULT"] == "v02pilot_02-channel-normalization"
    assert defaults["ARM_WRAPPER_DEFAULT"] == "arms/E-ai-engineering-skills.md"
    assert defaults["EXPECTED_STARTER_VERIFY_FAILURE_DEFAULT"] == "true"


def test_task3_defaults_are_cataloged():
    defaults = resolve_defaults("03-refund-grain", "E-ai-engineering-skills")

    assert defaults["TASK_ID_DEFAULT"] == "03-refund-grain"
    assert defaults["TASK_NAME_DEFAULT"] == "Product Refund Grain Regression"
    assert defaults["STARTER_DEFAULT"] == "tasks/03-refund-grain/starter_repo"
    assert defaults["TASK_PROMPT_DEFAULT"] == "tasks/03-refund-grain/starter_repo/TASK.md"
    assert defaults["MANIFEST_DEFAULT"] == "tasks/03-refund-grain/task_output_manifest.yml"
    assert defaults["HIDDEN_EVALUATOR_MODULE_DEFAULT"] == "benchmark_harness.evaluators.task3_hidden_evaluator"
    assert defaults["RUN_PREFIX_DEFAULT"] == "v03pilot_03-refund-grain"
    assert defaults["ARM_WRAPPER_DEFAULT"] == "arms/E-ai-engineering-skills.md"
    assert defaults["EXPECTED_STARTER_VERIFY_FAILURE_DEFAULT"] == "true"
