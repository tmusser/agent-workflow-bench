from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from activation_metrics.load import load_events, load_users  # noqa: E402
from activation_metrics.report import build_activation_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a starter activation report.")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--definition", required=True, choices=["v1", "v2"])
    parser.add_argument("--month", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    users = load_users(data_dir)
    events = load_events(data_dir)
    report = build_activation_report(users, events, args.month, args.definition)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(out_path, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
