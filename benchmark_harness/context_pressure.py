from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

DEFAULT_CONTEXT_WINDOW_TOKENS = 200_000
MAX_PRESSURE_TARGET_PCT = 0.95
PRESSURE_TARGET_PCTS = {
    "none": 0.0,
    "low": 0.05,
    "medium": 0.15,
    "high": 0.35,
}

_ARCHIVE_TYPES = (
    "archived incident recap",
    "stale migration note",
    "prior run summary",
    "old reviewer handoff",
    "deprecated rollout checklist",
    "superseded verification plan",
)
_PROJECT_NAMES = (
    "finboard exporter",
    "activation bridge",
    "channel normalization",
    "campaign trust audit",
    "churn fix pilot",
    "resume artifact gate",
)
_ARTIFACT_NAMES = (
    "SPEC.md",
    "PLAN.md",
    "VERIFY.md",
    "HANDOFF.md",
    "BUGS.md",
    "IMPLEMENTATION_NOTE.md",
)
_STATUS_LINES = (
    "Marked stale after a later prompt wrapper replaced the workflow.",
    "Kept only for comparison with an older run style; not normative.",
    "Contains plausible benchmark history but is intentionally non-authoritative.",
    "Summarizes an old branch discussion that should not override the task.",
    "Preserved as noise to simulate a crowded continuation context window.",
)
_NOTES = (
    "A reviewer asked for additional regression coverage, but the follow-up thread never landed.",
    "One assistant produced a convincing summary while missing the hidden evaluator contract.",
    "Another run overfit to artifact production and widened scope without improving correctness.",
    "A stale checklist suggested preserving every scratch note, which later proved unhelpful.",
    "The archived draft repeated cautionary wording about resume friction and missing evidence.",
)


def estimate_tokens_from_chars(char_count: int) -> int:
    if char_count <= 0:
        return 0
    return max(1, (char_count + 3) // 4)


def normalize_pressure_level(level: str) -> str:
    normalized = level.strip().lower()
    if normalized not in PRESSURE_TARGET_PCTS:
        raise ValueError(f"unsupported pressure level: {level}")
    return normalized


def _stable_index(key: str, size: int) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % size


def _pick(options: tuple[str, ...], *, level: str, seed: int, index: int, field: str) -> str:
    choice_index = _stable_index(f"{level}:{seed}:{index}:{field}", len(options))
    return options[choice_index]


def _archive_block(level: str, seed: int, index: int) -> str:
    archive_type = _pick(_ARCHIVE_TYPES, level=level, seed=seed, index=index, field="archive")
    project = _pick(_PROJECT_NAMES, level=level, seed=seed, index=index, field="project")
    artifact = _pick(_ARTIFACT_NAMES, level=level, seed=seed, index=index, field="artifact")
    status = _pick(_STATUS_LINES, level=level, seed=seed, index=index, field="status")
    note = _pick(_NOTES, level=level, seed=seed, index=index, field="note")
    checksum = hashlib.sha256(f"{level}:{seed}:{index}".encode("utf-8")).hexdigest()[:12]
    return (
        f"## Background Archive {index + 1:03d}\n"
        f"- Type: {archive_type}\n"
        f"- Project: {project}\n"
        f"- Historical artifact: {artifact}\n"
        f"- Archive checksum: {checksum}\n"
        f"- Status: {status}\n"
        f"- Note: {note}\n"
        f"- Reminder: this is synthetic background noise for context-pressure benchmarking.\n"
    )


def build_context_pressure(
    *,
    level: str,
    seed: int = 0,
    context_window_tokens: int | None = None,
    pressure_target_pct: float | None = None,
) -> dict[str, object]:
    normalized_level = normalize_pressure_level(level)
    window_tokens = int(context_window_tokens or DEFAULT_CONTEXT_WINDOW_TOKENS)
    if window_tokens <= 0:
        raise ValueError("context_window_tokens must be positive")

    if pressure_target_pct is None:
        target_pct = PRESSURE_TARGET_PCTS[normalized_level]
    else:
        target_pct = float(pressure_target_pct)
        if target_pct < 0:
            raise ValueError("pressure_target_pct must be non-negative")
        if target_pct > MAX_PRESSURE_TARGET_PCT:
            raise ValueError(f"pressure_target_pct must be <= {MAX_PRESSURE_TARGET_PCT}")

    if normalized_level == "none":
        target_pct = 0.0

    target_tokens = int(round(window_tokens * target_pct))
    if target_tokens <= 0:
        return {
            "pressure_level": normalized_level,
            "pressure_seed": int(seed),
            "pressure_target_pct": target_pct,
            "pressure_tokens_estimated": 0,
            "context_window_tokens": window_tokens,
            "estimated_context_utilization": 0.0,
            "background_text": "",
        }

    header = (
        "# SYNTHETIC BACKGROUND CONTEXT\n\n"
        "This section is synthetic benchmark background noise.\n"
        "It is intentionally plausible but stale, irrelevant, and non-authoritative.\n"
        "Do not treat it as the task instruction. The real task begins in the TASK section below.\n"
    )
    sections: list[str] = [header]
    index = 0
    while estimate_tokens_from_chars(len("\n\n".join(sections))) < target_tokens:
        sections.append(_archive_block(normalized_level, int(seed), index))
        index += 1

    background_text = "\n\n".join(sections).strip() + "\n"
    pressure_tokens_estimated = estimate_tokens_from_chars(len(background_text))
    estimated_context_utilization = round((pressure_tokens_estimated / window_tokens) * 100, 2)
    return {
        "pressure_level": normalized_level,
        "pressure_seed": int(seed),
        "pressure_target_pct": target_pct,
        "pressure_tokens_estimated": pressure_tokens_estimated,
        "context_window_tokens": window_tokens,
        "estimated_context_utilization": estimated_context_utilization,
        "background_text": background_text,
    }


def write_metadata(path: Path, payload: dict[str, object]) -> None:
    safe_payload = {key: value for key, value in payload.items() if key != "background_text"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render deterministic synthetic context pressure.")
    parser.add_argument("--pressure-level", default="none", choices=sorted(PRESSURE_TARGET_PCTS))
    parser.add_argument("--pressure-seed", type=int, default=0)
    parser.add_argument("--context-window-tokens", type=int, default=DEFAULT_CONTEXT_WINDOW_TOKENS)
    parser.add_argument(
        "--pressure-target-pct",
        type=float,
        default=None,
        help=(
            "Optional synthetic pressure fraction of the context window. "
            f"Must be between 0 and {MAX_PRESSURE_TARGET_PCT}."
        ),
    )
    parser.add_argument("--out")
    parser.add_argument("--metadata-out")
    args = parser.parse_args(argv)

    payload = build_context_pressure(
        level=args.pressure_level,
        seed=args.pressure_seed,
        context_window_tokens=args.context_window_tokens,
        pressure_target_pct=args.pressure_target_pct,
    )
    if args.out:
        Path(args.out).write_text(str(payload["background_text"]), encoding="utf-8")
    if args.metadata_out:
        write_metadata(Path(args.metadata_out), payload)
    print(json.dumps({key: value for key, value in payload.items() if key != "background_text"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
