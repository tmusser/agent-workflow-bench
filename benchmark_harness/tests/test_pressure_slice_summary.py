from __future__ import annotations

from benchmark_harness.pressure_slice_summary import render_pressure_slice_table


def test_pressure_slice_summary_renders_pressure_and_latency_rows():
    rows = [
        {
            "task_slug": "04-impossible-churn",
            "arm_slug": "A-baseline",
            "pressure_level": "none",
            "pressure_seed": 0,
            "pressure_tokens_estimated": 0,
            "estimated_context_utilization": 0.0,
            "max_context_utilization": None,
            "initial_verify_exit": 0,
            "initial_hidden_exit": 0,
            "initial_green": True,
            "full_resume_green": True,
            "stripped_resume_green": True,
            "artifact_mechanism_active": False,
            "skill_runtime_proof_valid": False,
            "initial_solution_latency_observable": False,
            "initial_actual_turns": 21,
            "initial_first_functional_green_turn": None,
            "initial_first_bench_ready_green_turn": None,
            "initial_turns_after_first_functional_green": None,
            "finalizer_total_turns": 0,
            "finalizer_total_wall_seconds": 0.0,
            "finalizer_total_cost_usd": 0.0,
        },
        {
            "task_slug": "04-impossible-churn",
            "arm_slug": "E-ai-engineering-skills",
            "pressure_level": "high",
            "pressure_seed": 7,
            "pressure_tokens_estimated": 6500,
            "estimated_context_utilization": 32.5,
            "max_context_utilization": 40.0,
            "initial_verify_exit": 0,
            "initial_hidden_exit": 1,
            "initial_green": False,
            "full_resume_green": False,
            "stripped_resume_green": False,
            "artifact_mechanism_active": True,
            "skill_runtime_proof_valid": True,
            "initial_solution_latency_observable": True,
            "initial_actual_turns": 18,
            "initial_first_functional_green_turn": 9,
            "initial_first_bench_ready_green_turn": 11,
            "initial_turns_after_first_functional_green": 9,
            "finalizer_total_turns": 4,
            "finalizer_total_wall_seconds": 8.25,
            "finalizer_total_cost_usd": 0.0123,
        },
    ]

    table = render_pressure_slice_table(rows, task_slug="04-impossible-churn")

    assert "| task_slug | arm_slug | pressure_level |" in table
    assert "04-impossible-churn" in table
    assert "none" in table
    assert "high" in table
    assert "pass" in table
    assert "fail" in table
    assert "?" in table


def test_pressure_slice_summary_handles_missing_actual_usage():
    rows = [
        {
            "task_slug": "04-impossible-churn",
            "arm_slug": "A-baseline",
            "pressure_level": "medium",
            "pressure_seed": 7,
            "pressure_tokens_estimated": 4879,
            "estimated_context_utilization": 15.25,
            "initial_verify_exit": 0,
            "initial_hidden_exit": 0,
            "initial_green": True,
            "full_resume_green": True,
            "stripped_resume_green": True,
            "artifact_mechanism_active": False,
            "skill_runtime_proof_valid": False,
            "initial_solution_latency_observable": True,
            "initial_actual_turns": 19,
            "initial_first_functional_green_turn": 8,
            "initial_first_bench_ready_green_turn": 10,
            "initial_turns_after_first_functional_green": 11,
            "finalizer_total_turns": 0,
            "finalizer_total_wall_seconds": 0.0,
            "finalizer_total_cost_usd": 0.0,
        }
    ]

    table = render_pressure_slice_table(rows)

    assert "4879" in table
    assert "15.25" in table
    assert "?" in table
    assert "medium" in table
