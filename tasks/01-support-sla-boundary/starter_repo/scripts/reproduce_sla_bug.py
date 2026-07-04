from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supportops.load import load_tickets  # noqa: E402
from supportops.metrics import add_sla_fields  # noqa: E402
from supportops.report import weekly_sla_report  # noqa: E402


def main() -> int:
    tickets = load_tickets(ROOT / "fixtures" / "tickets.csv")
    enriched = add_sla_fields(tickets)
    exact_boundary = enriched[enriched["response_hours"] == enriched["sla_hours"]]

    print("Exact-boundary SLA rows:")
    print(exact_boundary[["ticket_id", "priority", "response_hours", "sla_hours", "sla_breached"]])
    print()
    print("Weekly SLA report:")
    print(weekly_sla_report(ROOT / "fixtures"))

    if exact_boundary["sla_breached"].any():
        bad = exact_boundary[exact_boundary["sla_breached"]]["ticket_id"].tolist()
        print(f"BUG: exact-boundary tickets counted as breached: {bad}", file=sys.stderr)
        return 1

    print("No exact-boundary SLA breach detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
