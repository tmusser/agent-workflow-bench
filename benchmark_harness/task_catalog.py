from __future__ import annotations

import argparse
import shlex
from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class TaskConfig:
    task_slug: str
    task_id: str
    task_name: str
    starter_repo: str
    task_prompt: str
    manifest: str
    hidden_evaluator_module: str
    run_prefix: str
    expected_starter_verify_failure: bool
    resume_evaluator_module: str | None = None
    fresh_session_prompt: str = "benchmark_harness/protocols/FRESH_SESSION_PROMPT.md"
    arm_wrapper_overrides: Mapping[str, str] = field(default_factory=dict)


TASKS: dict[str, TaskConfig] = {
    "01-support-sla-boundary": TaskConfig(
        task_slug="01-support-sla-boundary",
        task_id="01-sla-boundary",
        task_name="Support SLA Boundary Regression",
        starter_repo="tasks/01-support-sla-boundary/starter_repo",
        task_prompt="tasks/01-support-sla-boundary/starter_repo/TASK.md",
        manifest="tasks/01-support-sla-boundary/task_output_manifest.yml",
        hidden_evaluator_module="benchmark_harness.evaluators.task1_hidden_evaluator",
        run_prefix="v01pilot_01-sla-boundary",
        expected_starter_verify_failure=True,
    ),
    "02-channel-normalization": TaskConfig(
        task_slug="02-channel-normalization",
        task_id="02-channel-normalization",
        task_name="Campaign Channel Normalization",
        starter_repo="tasks/02-channel-normalization/starter_repo",
        task_prompt="tasks/02-channel-normalization/starter_repo/TASK.md",
        manifest="tasks/02-channel-normalization/task_output_manifest.yml",
        hidden_evaluator_module="benchmark_harness.evaluators.task2_hidden_evaluator",
        run_prefix="v02pilot_02-channel-normalization",
        expected_starter_verify_failure=True,
    ),
    "03-refund-grain": TaskConfig(
        task_slug="03-refund-grain",
        task_id="03-refund-grain",
        task_name="Product Refund Grain Regression",
        starter_repo="tasks/03-refund-grain/starter_repo",
        task_prompt="tasks/03-refund-grain/starter_repo/TASK.md",
        manifest="tasks/03-refund-grain/task_output_manifest.yml",
        hidden_evaluator_module="benchmark_harness.evaluators.task3_hidden_evaluator",
        run_prefix="v03pilot_03-refund-grain",
        expected_starter_verify_failure=True,
    ),
    "04-impossible-churn": TaskConfig(
        task_slug="04-impossible-churn",
        task_id="04-bugfix",
        task_name="Impossible Churn Regression",
        starter_repo="tasks/04-impossible-churn/starter_repo",
        task_prompt="tasks/04-impossible-churn/starter_repo/TASK.md",
        manifest="tasks/04-impossible-churn/task_output_manifest.yml",
        hidden_evaluator_module="benchmark_harness.evaluators.task4_hidden_evaluator",
        run_prefix="v04pilot_04-bugfix",
        expected_starter_verify_failure=True,
    ),
    "05-fake-data-analysis": TaskConfig(
        task_slug="05-fake-data-analysis",
        task_id="05-fake-data",
        task_name="Fake Data Campaign Lift Trust",
        starter_repo="tasks/05-fake-data-analysis/starter_repo",
        task_prompt="tasks/05-fake-data-analysis/starter_repo/TASK.md",
        manifest="tasks/05-fake-data-analysis/task_output_manifest.yml",
        hidden_evaluator_module="benchmark_harness.evaluators.task5_hidden_evaluator",
        run_prefix="v05pilot_05-fake-data",
        expected_starter_verify_failure=False,
        arm_wrapper_overrides={
            "E-ai-engineering-skills": "arms/E-ai-engineering-skills-task5.md",
        },
    ),
    "06-activation-metric-migration": TaskConfig(
        task_slug="06-activation-metric-migration",
        task_id="06-activation",
        task_name="Activation Metric v2 Migration",
        starter_repo="tasks/06-activation-metric-migration/starter_repo",
        task_prompt="tasks/06-activation-metric-migration/starter_repo/TASK.md",
        manifest="tasks/06-activation-metric-migration/task_output_manifest.yml",
        hidden_evaluator_module="benchmark_harness.evaluators.task6_hidden_evaluator",
        run_prefix="v06pilot_06-activation",
        expected_starter_verify_failure=True,
        arm_wrapper_overrides={
            "B-strong-no-skill": "arms/B-strong-no-skill-task6.md",
            "E-ai-engineering-skills": "arms/E-ai-engineering-skills-task6.md",
        },
    ),
    "07-dashboard-export-scope-pressure": TaskConfig(
        task_slug="07-dashboard-export-scope-pressure",
        task_id="07-dashboard-export",
        task_name="Finance Weekly CSV Export",
        starter_repo="tasks/07-dashboard-export-scope-pressure/starter_repo",
        task_prompt="tasks/07-dashboard-export-scope-pressure/starter_repo/TASK.md",
        manifest="tasks/07-dashboard-export-scope-pressure/task_output_manifest.yml",
        hidden_evaluator_module="benchmark_harness.evaluators.task7_hidden_evaluator",
        resume_evaluator_module="benchmark_harness.evaluators.task7_resume_evaluator",
        fresh_session_prompt="benchmark_harness/protocols/FRESH_SESSION_PROMPT_TASK7.md",
        run_prefix="v07pilot_07-dashboard-export",
        expected_starter_verify_failure=True,
        arm_wrapper_overrides={
            "B-baseline": "arms/B-strong-no-skill-task7.md",
            "B-strong-no-skill": "arms/B-strong-no-skill-task7.md",
            "E-ai-engineering-skills": "arms/E-ai-engineering-skills-task7.md",
        },
    ),
}


def resolve_task_config(task_slug: str) -> TaskConfig:
    try:
        return TASKS[task_slug]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise KeyError(f"unknown task slug: {task_slug}") from exc


def resolve_defaults(task_slug: str, arm_slug: str) -> dict[str, str]:
    task = resolve_task_config(task_slug)
    arm_wrapper = task.arm_wrapper_overrides.get(arm_slug, f"arms/{arm_slug}.md")
    return {
        "TASK_ID_DEFAULT": task.task_id,
        "TASK_NAME_DEFAULT": task.task_name,
        "STARTER_DEFAULT": task.starter_repo,
        "TASK_PROMPT_DEFAULT": task.task_prompt,
        "MANIFEST_DEFAULT": task.manifest,
        "HIDDEN_EVALUATOR_MODULE_DEFAULT": task.hidden_evaluator_module,
        "RESUME_HIDDEN_EVALUATOR_MODULE_DEFAULT": task.resume_evaluator_module or task.hidden_evaluator_module,
        "FRESH_SESSION_PROMPT_DEFAULT": task.fresh_session_prompt,
        "RUN_PREFIX_DEFAULT": task.run_prefix,
        "ARM_WRAPPER_DEFAULT": arm_wrapper,
        "EXPECTED_STARTER_VERIFY_FAILURE_DEFAULT": "true" if task.expected_starter_verify_failure else "false",
    }


def shell_exports(task_slug: str, arm_slug: str) -> str:
    defaults = resolve_defaults(task_slug, arm_slug)
    return "\n".join(f"{key}={shlex.quote(value)}" for key, value in defaults.items()) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print task defaults for the pilot smoke helper.")
    parser.add_argument("--task-slug", required=True)
    parser.add_argument("--arm-slug", default="A-baseline")
    args = parser.parse_args(argv)
    print(shell_exports(args.task_slug, args.arm_slug), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
