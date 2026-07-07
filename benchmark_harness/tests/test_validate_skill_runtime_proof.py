from __future__ import annotations

from pathlib import Path

import pytest

from benchmark_harness.validate_skill_runtime_proof import main, validate


VALID_PROOF = """# Skill Runtime Proof

## Run
- Run ID: r1
- Arm: B
- Task: 04-bugfix — Impossible Churn Regression
- Repeat: 1

## Skill source
- Repo URL: https://example.com/repo.git
- Pinned commit SHA: 0123456789abcdef0123456789abcdef01234567
- Local path: /tmp/skills/repo
- Install command: cp -R /tmp/skills/repo ~/.claude/skills/repo
- Install stdout/stderr path: benchmark-data/runs/r1/install.txt

## Activation
- Agent CLI: claude
- Activation mechanism: skill directory mounted before run
- Prompt wrapper path: arms/B-matt-pocock.md
- Agent-visible skill files: ~/.claude/skills/repo/README.md
- Environment variables relevant to skill loading: none

## Pre-run availability check
- Command run: test -f ~/.claude/skills/repo/README.md
- Result: available
- Evidence path: benchmark-data/runs/r1/skill_available.txt

## During-run evidence
- Invocation evidence level: agent_declared
- Did the agent mention or invoke the skill? yes/no/unclear
- Evidence: benchmark-data/runs/r1/stdout.txt
- Notes: none

## Post-run caveat
- Could a bad result be due to the skill not being loaded? no
- Reviewer notes: none
"""


def _proof_with_level(level: str) -> str:
    return VALID_PROOF.replace("- Invocation evidence level: agent_declared", f"- Invocation evidence level: {level}")


@pytest.mark.parametrize("level", ["availability_only", "artifact_inferred", "agent_declared"])
def test_allowed_invocation_evidence_levels_pass(tmp_path: Path, level: str):
    path = tmp_path / "SKILL_RUNTIME_PROOF.md"
    path.write_text(_proof_with_level(level), encoding="utf-8")

    assert validate(path) == []


def test_placeholders_fail_strict_validation(tmp_path: Path):
    path = tmp_path / "SKILL_RUNTIME_PROOF.md"
    path.write_text(VALID_PROOF.replace("0123456789abcdef0123456789abcdef01234567", "TO_BE_FILLED"), encoding="utf-8")

    issues = validate(path)

    assert "field is empty or placeholder: Pinned commit SHA" in issues


def test_template_mode_allows_blank_template(tmp_path: Path):
    path = tmp_path / "SKILL_RUNTIME_PROOF_TEMPLATE.md"
    path.write_text("""# Skill Runtime Proof

## Skill source
- Repo URL:
- Pinned commit SHA:
- Install command:

## Activation
- Agent CLI:
- Activation mechanism:

## Pre-run availability check
- Command run:
- Result:

## During-run evidence
- Invocation evidence level:
""", encoding="utf-8")

    assert validate(path, allow_template=True) == []
    assert validate(path) != []


def test_template_task_field_is_placeholder():
    template = Path(__file__).resolve().parents[1] / "templates" / "SKILL_RUNTIME_PROOF_TEMPLATE.md"
    assert "- Task: TO_BE_FILLED" in template.read_text(encoding="utf-8")


def test_invalid_invocation_evidence_level_fails(tmp_path: Path):
    path = tmp_path / "SKILL_RUNTIME_PROOF.md"
    path.write_text(
        _proof_with_level("guessed"),
        encoding="utf-8",
    )

    issues = validate(path)

    assert (
        "Invocation evidence level must be one of: availability_only, artifact_inferred, agent_declared, runtime_hook"
        in issues
    )


def test_runtime_hook_fails_by_default(tmp_path: Path):
    path = tmp_path / "SKILL_RUNTIME_PROOF.md"
    path.write_text(_proof_with_level("runtime_hook"), encoding="utf-8")

    issues = validate(path)

    assert (
        "Invocation evidence level runtime_hook requires --allow-runtime-hook until true runtime-hook evidence is supported"
        in issues
    )


def test_runtime_hook_passes_with_explicit_opt_in(tmp_path: Path):
    path = tmp_path / "SKILL_RUNTIME_PROOF.md"
    path.write_text(_proof_with_level("runtime_hook"), encoding="utf-8")

    assert validate(path, allow_runtime_hook=True) == []


def test_runtime_hook_passes_with_cli_opt_in(tmp_path: Path):
    path = tmp_path / "SKILL_RUNTIME_PROOF.md"
    path.write_text(_proof_with_level("runtime_hook"), encoding="utf-8")

    assert main([str(path), "--allow-runtime-hook"]) == 0
