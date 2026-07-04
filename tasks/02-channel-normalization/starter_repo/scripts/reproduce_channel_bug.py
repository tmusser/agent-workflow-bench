from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acquisition.report import weekly_channel_report  # noqa: E402


EXPECTED = {
    "email": 2,
    "paid_search": 2,
    "referral": 1,
    "unknown": 1,
}


def main() -> int:
    report = weekly_channel_report(ROOT / "fixtures")
    print("Weekly channel report:")
    print(report)

    actual = dict(zip(report["channel"], report["signups"], strict=False))
    errors = []
    for channel, expected_count in EXPECTED.items():
        actual_count = int(actual.get(channel, 0))
        if actual_count != expected_count:
            errors.append(f"{channel} expected {expected_count}, got {actual_count}")

    unexpected = sorted(set(actual) - set(EXPECTED))
    if unexpected:
        errors.append(f"unexpected channel labels: {unexpected}")

    if errors:
        for error in errors:
            print(f"BUG: {error}", file=sys.stderr)
        return 1

    print("No channel normalization bug detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
