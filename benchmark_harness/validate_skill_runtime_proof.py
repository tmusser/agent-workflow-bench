from __future__ import annotations

import argparse
import re
from pathlib import Path

REQUIRED_MARKERS = [
    "## Skill source",
    "- Repo URL:",
    "- Pinned commit SHA:",
    "- Install command:",
    "## Activation",
    "- Agent CLI:",
    "- Activation mechanism:",
    "## Pre-run availability check",
    "- Command run:",
    "- Result:",
    "## During-run evidence",
    "- Invocation evidence level:",
]

STRICT_FIELDS = [
    "Repo URL",
    "Pinned commit SHA",
    "Local path",
    "Install command",
    "Install stdout/stderr path",
    "Agent CLI",
    "Activation mechanism",
    "Prompt wrapper path",
    "Agent-visible skill files",
    "Command run",
    "Result",
    "Evidence path",
    "Invocation evidence level",
]

ALLOWED_INVOCATION_EVIDENCE_LEVELS = {
    "availability_only",
    "artifact_inferred",
    "agent_declared",
    "runtime_hook",
}

PLACEHOLDER_VALUES = {
    "",
    "to_be_filled",
    "tbd",
    "todo",
    "none",
    "n/a",
    "na",
    "unknown",
    "unclear",
    "...",
    "<to be filled>",
    "<fill me>",
}

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _field_value(text: str, field: str) -> str | None:
    prefix = f"- {field}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def _is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().strip("`'").lower()
    return normalized in PLACEHOLDER_VALUES or normalized.startswith("to be filled")


def _agent_family(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    if not normalized:
        return None
    if "codex" in normalized:
        return "codex"
    if "claude" in normalized:
        return "claude"
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or None


def validate(
    path: Path,
    *,
    allow_template: bool = False,
    allow_runtime_hook: bool = False,
    expected_agent_cli: str | None = None,
) -> list[str]:
    text = path.read_text(encoding="utf-8")
    issues = [f"missing marker: {marker}" for marker in REQUIRED_MARKERS if marker not in text]
    if allow_template:
        return issues

    for field in STRICT_FIELDS:
        value = _field_value(text, field)
        if _is_placeholder(value):
            issues.append(f"field is empty or placeholder: {field}")

    sha = _field_value(text, "Pinned commit SHA")
    if sha and not _is_placeholder(sha) and not SHA_RE.fullmatch(sha):
        issues.append("Pinned commit SHA must be a 40-character lowercase hex SHA")

    result = (_field_value(text, "Result") or "").strip().lower()
    if result and result not in {"pass", "passed", "success", "available", "ok", "yes"}:
        issues.append("Pre-run availability Result must indicate a successful availability check")

    invocation_evidence_level = (_field_value(text, "Invocation evidence level") or "").strip().lower()
    if invocation_evidence_level == "runtime_hook" and not allow_runtime_hook:
        issues.append(
            "Invocation evidence level runtime_hook requires --allow-runtime-hook until true runtime-hook evidence is supported"
        )
    elif invocation_evidence_level and invocation_evidence_level not in ALLOWED_INVOCATION_EVIDENCE_LEVELS:
        issues.append(
            "Invocation evidence level must be one of: availability_only, artifact_inferred, agent_declared, runtime_hook"
        )

    expected_family = _agent_family(expected_agent_cli)
    actual_agent_cli = _field_value(text, "Agent CLI")
    actual_family = _agent_family(actual_agent_cli)
    if expected_family and actual_family != expected_family:
        issues.append(
            f"Agent CLI {actual_agent_cli or 'missing'} does not match expected runner family {expected_family}"
        )

    environment = (_field_value(text, "Environment variables relevant to skill loading") or "").lower()
    activation = (_field_value(text, "Activation mechanism") or "").lower()
    if expected_family == "codex":
        if "claude_plugin_dir" in environment:
            issues.append("Codex proof must not claim CLAUDE_PLUGIN_DIR as its skill-loading environment")
        if "namespaced skill invocation" in activation:
            issues.append(
                "Codex proof must not claim namespaced skill invocation without provider-native runtime support"
            )

    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a SKILL_RUNTIME_PROOF.md file.")
    parser.add_argument("path")
    parser.add_argument(
        "--allow-runtime-hook",
        action="store_true",
        help="Allow Invocation evidence level: runtime_hook for repositories with real runtime-hook evidence.",
    )
    parser.add_argument(
        "--expected-agent-cli",
        help="Validate that Agent CLI and loading claims match the actual runner family.",
    )
    parser.add_argument(
        "--allow-template",
        action="store_true",
        help="Only validate required markers; use for the blank template, not real run proofs.",
    )
    args = parser.parse_args(argv)
    issues = validate(
        Path(args.path),
        allow_template=args.allow_template,
        allow_runtime_hook=args.allow_runtime_hook,
        expected_agent_cli=args.expected_agent_cli,
    )
    if issues:
        for issue in issues:
            print(issue)
        return 1
    print("Skill runtime proof validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
