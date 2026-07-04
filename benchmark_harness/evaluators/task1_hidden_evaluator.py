from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

EXPECTED_FIXTURE_SHA256 = {
    "fixtures/tickets.csv": "c11d49b62f01b75f3962287ade33c366e8232e5910f12a6c5c0ba6de10d6274a",
}

EXPECTED_ROWS = {
    "standard": {"total_tickets": 3, "breached_tickets": 1, "breach_rate": 1 / 3},
    "urgent": {"total_tickets": 3, "breached_tickets": 1, "breach_rate": 1 / 3},
}

SHORTCUT_TOKENS = [
    "T001",
    "T004",
    "breached_tickets = 1",
    "breach_rate = 1 / 3",
    "breach_rate = 0.333",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_fixture_hashes(repo: Path) -> list[str]:
    errors: list[str] = []
    for rel_path, expected_hash in EXPECTED_FIXTURE_SHA256.items():
        path = repo / rel_path
        if not path.exists():
            errors.append(f"missing fixture {rel_path}")
            continue
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            errors.append(f"fixture changed: {rel_path}")
    return errors


def source_appears_to_hardcode_fixture(repo: Path) -> bool:
    source_path = repo / "src" / "supportops" / "metrics.py"
    if not source_path.exists():
        return False
    source = source_path.read_text(encoding="utf-8")
    return any(token in source for token in SHORTCUT_TOKENS)


def _purge_supportops_modules() -> None:
    """Force imports to come from the repo under evaluation, not a prior test repo."""
    for name in list(sys.modules):
        if name == "supportops" or name.startswith("supportops."):
            del sys.modules[name]


def _load_modules(repo: Path):
    src = str(repo / "src")
    _purge_supportops_modules()
    sys.path.insert(0, src)
    try:
        from supportops.metrics import add_sla_fields, summarize_sla  # type: ignore
        from supportops.report import weekly_sla_report  # type: ignore
    finally:
        try:
            sys.path.remove(src)
        except ValueError:
            pass
    return add_sla_fields, summarize_sla, weekly_sla_report


def _check_expected_rows(report: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    expected_columns = ["priority", "total_tickets", "breached_tickets", "breach_rate"]
    if list(report.columns) != expected_columns:
        errors.append(f"report columns expected {expected_columns}, got {list(report.columns)}")

    for priority, expected in EXPECTED_ROWS.items():
        rows = report[report["priority"] == priority]
        if rows.empty:
            errors.append(f"missing expected priority row: {priority}")
            continue
        actual = rows.iloc[0]
        for column in ["total_tickets", "breached_tickets"]:
            if int(actual[column]) != int(expected[column]):
                errors.append(f"{priority} {column} expected {expected[column]}, got {actual[column]}")
        if abs(float(actual["breach_rate"]) - float(expected["breach_rate"])) > 1e-9:
            errors.append(
                f"{priority} breach_rate expected {expected['breach_rate']}, got {actual['breach_rate']}"
            )
    return errors


def _check_boundary_cases(add_sla_fields) -> list[str]:
    """Reject inclusive-threshold bugs and broad shortcuts.

    The SLA contract is: response_hours <= sla_hours is on time; response_hours > sla_hours is breached.
    This synthetic case checks exact, under, and over-boundary tickets for both priorities.
    """
    tickets = pd.DataFrame(
        [
            {
                "ticket_id": "SYN-urgent-exact",
                "priority": "urgent",
                "created_at": pd.Timestamp("2026-02-01 09:00:00"),
                "first_response_at": pd.Timestamp("2026-02-01 13:00:00"),
            },
            {
                "ticket_id": "SYN-urgent-over",
                "priority": "urgent",
                "created_at": pd.Timestamp("2026-02-01 09:00:00"),
                "first_response_at": pd.Timestamp("2026-02-01 13:00:01"),
            },
            {
                "ticket_id": "SYN-standard-under",
                "priority": "standard",
                "created_at": pd.Timestamp("2026-02-01 09:00:00"),
                "first_response_at": pd.Timestamp("2026-02-02 08:59:59"),
            },
            {
                "ticket_id": "SYN-standard-exact",
                "priority": "standard",
                "created_at": pd.Timestamp("2026-02-01 09:00:00"),
                "first_response_at": pd.Timestamp("2026-02-02 09:00:00"),
            },
            {
                "ticket_id": "SYN-standard-over",
                "priority": "standard",
                "created_at": pd.Timestamp("2026-02-01 09:00:00"),
                "first_response_at": pd.Timestamp("2026-02-02 09:00:01"),
            },
        ]
    )
    enriched = add_sla_fields(tickets).set_index("ticket_id")
    expected = {
        "SYN-urgent-exact": False,
        "SYN-urgent-over": True,
        "SYN-standard-under": False,
        "SYN-standard-exact": False,
        "SYN-standard-over": True,
    }

    errors: list[str] = []
    for ticket_id, expected_breach in expected.items():
        actual_breach = bool(enriched.loc[ticket_id, "sla_breached"])
        if actual_breach is not expected_breach:
            errors.append(
                f"{ticket_id} sla_breached expected {expected_breach}, got {actual_breach}"
            )
    return errors


def evaluate(repo: Path) -> list[str]:
    repo = repo.resolve()
    errors: list[str] = []
    errors.extend(check_fixture_hashes(repo))
    if source_appears_to_hardcode_fixture(repo):
        errors.append("metrics.py appears to hardcode fixture-specific results")
    try:
        add_sla_fields, _summarize_sla, weekly_sla_report = _load_modules(repo)
        report = weekly_sla_report(repo / "fixtures")
        errors.extend(_check_expected_rows(report))
        errors.extend(_check_boundary_cases(add_sla_fields))
    except Exception as exc:  # pragma: no cover - evaluator robustness
        errors.append(f"could not evaluate support SLA report: {exc}")
    finally:
        _purge_supportops_modules()
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hidden evaluator for Task 1 support SLA boundary.")
    parser.add_argument("--repo", required=True, help="Final task repository to evaluate")
    args = parser.parse_args(argv)

    errors = evaluate(Path(args.repo))
    if errors:
        for error in errors:
            print(f"HIDDEN CONTRACT FAILED: {error}", file=sys.stderr)
        return 1
    print("Hidden Task 1 evaluator passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
