from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

TASK7_SLUG = "07-dashboard-export-scope-pressure"
TASK7_B_ALIAS_WRAPPER = "arms/B-strong-no-skill-task7.md"
PROVENANCE_VERSION = "task7-run-provenance-v1"


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(_read_bytes(path))
    return digest.hexdigest()


def _context_mode(label: str) -> str:
    normalized = label.strip().lower()
    if normalized == "initial":
        return "initial"
    if normalized == "full resume":
        return "full resume"
    if normalized == "stripped resume":
        return "stripped resume"
    if normalized.endswith("resume"):
        return normalized
    return "unknown"


def _relative_or_resolved(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _resolved_arm_slug(task_slug: str, arm_wrapper_path: Path, requested_arm_slug: str) -> str:
    if task_slug == TASK7_SLUG and arm_wrapper_path.name == Path(TASK7_B_ALIAS_WRAPPER).name:
        return "B-strong-no-skill"
    return requested_arm_slug


def build_run_provenance(
    *,
    root_dir: Path,
    run_id: str,
    task_slug: str,
    arm_slug: str,
    arm_wrapper: str,
    task_prompt: str,
    resume_prompt: str,
    label: str,
    model: str,
    effort: str,
    max_turns: int,
    permission_mode: str,
    output_format: str,
    pressure_level: str = "none",
    pressure_seed: int = 0,
    pressure_tokens_estimated: int = 0,
    context_window_tokens: int | None = None,
    estimated_context_utilization: float = 0.0,
    pressure_target_pct: float | None = None,
) -> dict[str, object]:
    root_dir = root_dir.resolve()
    arm_wrapper_path = (root_dir / arm_wrapper).resolve()
    task_prompt_path = (root_dir / task_prompt).resolve()
    resume_prompt_path = (root_dir / resume_prompt).resolve()

    if task_slug == TASK7_SLUG and arm_wrapper_path.name == "B-baseline.md":
        raise ValueError(
            f"Task 7 B runs must resolve to {TASK7_B_ALIAS_WRAPPER}, not arms/B-baseline.md"
        )
    if not arm_wrapper_path.exists():
        raise FileNotFoundError(f"missing arm wrapper: {arm_wrapper_path}")
    if not task_prompt_path.exists():
        raise FileNotFoundError(f"missing task prompt: {task_prompt_path}")
    if not resume_prompt_path.exists():
        raise FileNotFoundError(f"missing resume prompt: {resume_prompt_path}")

    resolved_arm_slug = _resolved_arm_slug(task_slug, arm_wrapper_path, arm_slug)
    alias_applied = task_slug == TASK7_SLUG and arm_slug == "B-baseline"
    provenance = {
        "provenance_version": PROVENANCE_VERSION,
        "run_id": run_id,
        "task_slug": task_slug,
        "arm_slug": arm_slug,
        "requested_arm_slug": arm_slug,
        "resolved_arm_slug": resolved_arm_slug,
        "canonical_arm_slug": resolved_arm_slug,
        "arm_slug_mismatch": arm_slug != resolved_arm_slug,
        "alias_applied": alias_applied,
        "alias_reason": (
            "Task 7 legacy B label maps to task-specific strong no-skill wrapper" if alias_applied else ""
        ),
        "label": label,
        "context_mode": _context_mode(label),
        "model": model,
        "effort": effort,
        "max_turns": int(max_turns),
        "permission_mode": permission_mode,
        "output_format": output_format,
        "pressure_level": pressure_level,
        "pressure_seed": int(pressure_seed),
        "pressure_tokens_estimated": int(pressure_tokens_estimated),
        "context_window_tokens": int(context_window_tokens) if context_window_tokens is not None else None,
        "estimated_context_utilization": float(estimated_context_utilization),
        "pressure_target_pct": pressure_target_pct,
        "arm_wrapper_path": _relative_or_resolved(arm_wrapper_path, root_dir),
        "arm_wrapper_sha256": _sha256(arm_wrapper_path),
        "task_prompt_path": _relative_or_resolved(task_prompt_path, root_dir),
        "task_prompt_sha256": _sha256(task_prompt_path),
        "resume_prompt_path": _relative_or_resolved(resume_prompt_path, root_dir),
        "resume_prompt_sha256": _sha256(resume_prompt_path),
    }
    return provenance


def write_run_provenance(path: Path, **kwargs: object) -> dict[str, object]:
    provenance = build_run_provenance(**kwargs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return provenance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write run provenance metadata for a pilot run.")
    parser.add_argument("--out", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-slug", required=True)
    parser.add_argument("--arm-slug", required=True)
    parser.add_argument("--arm-wrapper", required=True)
    parser.add_argument("--task-prompt", required=True)
    parser.add_argument("--resume-prompt", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--max-turns", required=True, type=int)
    parser.add_argument("--permission-mode", required=True)
    parser.add_argument("--output-format", required=True)
    parser.add_argument("--pressure-level", default="none")
    parser.add_argument("--pressure-seed", type=int, default=0)
    parser.add_argument("--pressure-tokens-estimated", type=int, default=0)
    parser.add_argument("--context-window-tokens", type=int, default=None)
    parser.add_argument("--estimated-context-utilization", type=float, default=0.0)
    parser.add_argument("--pressure-target-pct", type=float, default=None)
    args = parser.parse_args(argv)

    provenance = write_run_provenance(
        Path(args.out),
        root_dir=Path(args.root),
        run_id=args.run_id,
        task_slug=args.task_slug,
        arm_slug=args.arm_slug,
        arm_wrapper=args.arm_wrapper,
        task_prompt=args.task_prompt,
        resume_prompt=args.resume_prompt,
        label=args.label,
        model=args.model,
        effort=args.effort,
        max_turns=args.max_turns,
        permission_mode=args.permission_mode,
        output_format=args.output_format,
        pressure_level=args.pressure_level,
        pressure_seed=args.pressure_seed,
        pressure_tokens_estimated=args.pressure_tokens_estimated,
        context_window_tokens=args.context_window_tokens,
        estimated_context_utilization=args.estimated_context_utilization,
        pressure_target_pct=args.pressure_target_pct,
    )
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
