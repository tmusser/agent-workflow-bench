from __future__ import annotations

import argparse
import csv
from pathlib import Path

ARMS = [
    ("A", "No skill baseline", "arms/A-baseline.md"),
    ("B", "Matt Pocock skills", "arms/B-matt-pocock.md"),
    ("C", "Addy Osmani agent-skills", "arms/C-addy-osmani.md"),
    ("D", "Ponytail", "arms/D-ponytail.md"),
    ("E", "ai-engineering-skills", "arms/E-ai-engineering-skills.md"),
    ("F", "ai-engineering-skills + Ponytail", "arms/F-ai-engineering-skills-ponytail.md"),
]


def write_run_matrix(out: Path, repeats: int = 2) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "run_id",
                "task_id",
                "task_name",
                "arm_id",
                "arm_name",
                "arm_wrapper_path",
                "repeat",
                "initial_run_required",
                "full_resume_required",
                "artifact_stripped_resume_required",
            ],
        )
        writer.writeheader()
        for arm_id, arm_name, wrapper_path in ARMS:
            for repeat in range(1, repeats + 1):
                writer.writerow(
                    {
                        "run_id": f"v04pilot_04-bugfix_{arm_id}_r{repeat}",
                        "task_id": "04-bugfix",
                        "task_name": "Impossible Churn Regression",
                        "arm_id": arm_id,
                        "arm_name": arm_name,
                        "arm_wrapper_path": wrapper_path,
                        "repeat": repeat,
                        "initial_run_required": "true",
                        "full_resume_required": "true",
                        "artifact_stripped_resume_required": "true",
                    }
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create the v0.4.2 pilot run matrix.")
    parser.add_argument("--out", default="benchmark_harness/run_matrix.csv")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args(argv)
    write_run_matrix(Path(args.out), args.repeats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
