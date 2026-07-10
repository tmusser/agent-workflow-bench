from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    args = parser.parse_args()
    state = (args.repo / "state.txt").read_text(encoding="utf-8").strip()
    print(f"state={state}")
    return 0 if state == "green" else 1


if __name__ == "__main__":
    raise SystemExit(main())
