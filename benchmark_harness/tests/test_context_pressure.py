from __future__ import annotations

from benchmark_harness import context_pressure


def test_context_pressure_is_deterministic_for_level_and_seed():
    first = context_pressure.build_context_pressure(level="medium", seed=7, context_window_tokens=20_000)
    second = context_pressure.build_context_pressure(level="medium", seed=7, context_window_tokens=20_000)

    assert first == second
    assert first["pressure_tokens_estimated"] > 0
    assert "synthetic benchmark background noise" in str(first["background_text"]).lower()


def test_context_pressure_changes_with_seed():
    first = context_pressure.build_context_pressure(level="medium", seed=7, context_window_tokens=20_000)
    second = context_pressure.build_context_pressure(level="medium", seed=8, context_window_tokens=20_000)

    assert first["background_text"] != second["background_text"]


def test_none_pressure_produces_no_background():
    payload = context_pressure.build_context_pressure(level="none", seed=0, context_window_tokens=20_000)

    assert payload["background_text"] == ""
    assert payload["pressure_tokens_estimated"] == 0
    assert payload["estimated_context_utilization"] == 0.0
