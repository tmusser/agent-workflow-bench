from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from commerce.report import weekly_refund_report  # noqa: E402


EXPECTED = {
    "gadget": {"total_orders": 3, "refunded_orders": 2, "refund_rate": 2 / 3},
    "widget": {"total_orders": 3, "refunded_orders": 1, "refund_rate": 1 / 3},
}


def main() -> int:
    report = weekly_refund_report(ROOT / "fixtures")
    print("Weekly refund report:")
    print(report)

    errors = []
    for product, expected in EXPECTED.items():
        rows = report[report["product"] == product]
        if rows.empty:
            errors.append(f"missing product row: {product}")
            continue
        row = rows.iloc[0]
        for column in ["total_orders", "refunded_orders"]:
            actual = int(row[column])
            if actual != expected[column]:
                errors.append(f"{product} {column} expected {expected[column]}, got {actual}")
        if abs(float(row["refund_rate"]) - expected["refund_rate"]) > 1e-9:
            errors.append(f"{product} refund_rate expected {expected['refund_rate']}, got {row['refund_rate']}")

    if errors:
        for error in errors:
            print(f"BUG: {error}", file=sys.stderr)
        return 1

    print("No refund grain bug detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
