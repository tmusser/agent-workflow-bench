from __future__ import annotations

import argparse
from pathlib import Path


def render_prompt(common_wrapper: Path, arm_wrapper: Path, task_prompt: Path, out: Path) -> None:
    chunks = [
        ("COMMON RUNNER WRAPPER", common_wrapper.read_text(encoding="utf-8")),
        ("ARM WRAPPER", arm_wrapper.read_text(encoding="utf-8")),
        ("TASK", task_prompt.read_text(encoding="utf-8")),
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n\n".join(f"# {title}\n\n{body.strip()}" for title, body in chunks) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render an agent-visible prompt for one benchmark run.")
    parser.add_argument("--common-wrapper", default="common_wrapper.md")
    parser.add_argument("--arm-wrapper", required=True)
    parser.add_argument("--task-prompt", default="tasks/04-impossible-churn/starter_repo/TASK.md")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    render_prompt(Path(args.common_wrapper), Path(args.arm_wrapper), Path(args.task_prompt), Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
