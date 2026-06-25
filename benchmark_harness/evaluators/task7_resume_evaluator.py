from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark_harness.evaluators.task7_hidden_evaluator import evaluate as evaluate_hidden


def evaluate(repo: Path) -> dict[str, object]:
    return evaluate_hidden(repo, phase="resume")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Task 7 resume evaluator.")
    parser.add_argument("--repo", required=True, help="Repository to evaluate")
    args = parser.parse_args(argv)

    result = evaluate(Path(args.repo))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_green"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
