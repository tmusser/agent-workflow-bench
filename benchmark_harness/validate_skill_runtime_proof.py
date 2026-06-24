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
]

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


def validate(path: Path, *, allow_template: bool = False) -> list[str]:
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

    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a SKILL_RUNTIME_PROOF.md file.")
    parser.add_argument("path")
    parser.add_argument(
        "--allow-template",
        action="store_true",
        help="Only validate required markers; use for the blank template, not real run proofs.",
    )
    args = parser.parse_args(argv)
    issues = validate(Path(args.path), allow_template=args.allow_template)
    if issues:
        for issue in issues:
            print(issue)
        return 1
    print("Skill runtime proof validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
