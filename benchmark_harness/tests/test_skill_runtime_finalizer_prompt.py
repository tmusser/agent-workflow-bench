from __future__ import annotations

from pathlib import Path


def test_skill_runtime_finalizer_prompt_contains_strict_proof_schema():
    text = Path("benchmark_harness/protocols/SKILL_RUNTIME_FINALIZER_PROMPT.md").read_text(
        encoding="utf-8"
    )

    required = [
        "Do not run shell commands.",
        "The benchmark harness will validate",
        "# Skill Runtime Proof",
        "## Skill source",
        "- Repo URL:",
        "- Pinned commit SHA:",
        "## Activation",
        "- Agent CLI:",
        "- Activation mechanism:",
        "## Pre-run availability check",
        "- Command run:",
        "- Result:",
        "## During-run evidence",
        "- Invocation evidence level:",
        "Do not ask for command approval.",
        "Do not ask to run commands.",
    ]

    for needle in required:
        assert needle in text
