from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark_harness.context_pressure import build_context_pressure, write_metadata


def render_prompt(
    common_wrapper: Path,
    arm_wrapper: Path,
    task_prompt: Path,
    out: Path,
    *,
    pressure_level: str = "none",
    pressure_seed: int = 0,
    context_window_tokens: int | None = None,
    pressure_target_pct: float | None = None,
    metadata_out: Path | None = None,
) -> dict[str, object]:
    pressure = build_context_pressure(
        level=pressure_level,
        seed=pressure_seed,
        context_window_tokens=context_window_tokens,
        pressure_target_pct=pressure_target_pct,
    )
    chunks = [
        ("COMMON RUNNER WRAPPER", common_wrapper.read_text(encoding="utf-8")),
        ("ARM WRAPPER", arm_wrapper.read_text(encoding="utf-8")),
    ]
    if pressure["background_text"]:
        chunks.append(("SYNTHETIC BACKGROUND CONTEXT", str(pressure["background_text"]).strip()))
    chunks.append(("TASK", task_prompt.read_text(encoding="utf-8")))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n\n".join(f"# {title}\n\n{body.strip()}" for title, body in chunks) + "\n",
        encoding="utf-8",
    )
    if metadata_out is not None:
        write_metadata(metadata_out, pressure)
    return {key: value for key, value in pressure.items() if key != "background_text"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render an agent-visible prompt for one benchmark run.")
    parser.add_argument("--common-wrapper", default="common_wrapper.md")
    parser.add_argument("--arm-wrapper", required=True)
    parser.add_argument("--task-prompt", default="tasks/04-impossible-churn/starter_repo/TASK.md")
    parser.add_argument("--out", required=True)
    parser.add_argument("--pressure-level", default="none")
    parser.add_argument("--pressure-seed", type=int, default=0)
    parser.add_argument("--context-window-tokens", type=int, default=None)
    parser.add_argument("--pressure-target-pct", type=float, default=None)
    parser.add_argument("--metadata-out")
    args = parser.parse_args(argv)
    metadata = render_prompt(
        Path(args.common_wrapper),
        Path(args.arm_wrapper),
        Path(args.task_prompt),
        Path(args.out),
        pressure_level=args.pressure_level,
        pressure_seed=args.pressure_seed,
        context_window_tokens=args.context_window_tokens,
        pressure_target_pct=args.pressure_target_pct,
        metadata_out=Path(args.metadata_out) if args.metadata_out else None,
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
