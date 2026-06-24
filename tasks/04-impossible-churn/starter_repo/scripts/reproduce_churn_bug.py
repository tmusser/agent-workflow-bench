from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from churncalc.dashboard_adapter import get_march_enterprise_churn  # noqa: E402


def main() -> int:
    row = get_march_enterprise_churn(ROOT / "fixtures")
    print("March enterprise churn row:")
    print(row)
    churn_rate = float(row["churn_rate"])
    if churn_rate > 1.0:
        print(f"BUG: churn_rate is {churn_rate:.3f}, which is above 100%", file=sys.stderr)
        return 1
    print("No impossible churn detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
