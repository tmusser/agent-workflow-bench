from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

EXPECTED_FIXTURE_SHA256 = {
    "fixtures/leads.csv": "c96a72707f8db566a59011f08eb3000f4c89a5487ecb1ca7fd71ada4fcfcdb22",
}
EXPECTED_ROWS = {
    "email": 2,
    "paid_search": 2,
    "referral": 1,
    "unknown": 1,
}
SHORTCUT_TOKENS = ("L001", "L002", "L005", "email = 2", "paid_search = 2", "unknown = 1")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _purge_acquisition_modules() -> None:
    for name in list(sys.modules):
        if name == "acquisition" or name.startswith("acquisition."):
            del sys.modules[name]


def _load_modules(repo: Path):
    src = str(repo / "src")
    _purge_acquisition_modules()
    sys.path.insert(0, src)
    try:
        from acquisition.metrics import add_channel_fields, summarize_channels  # type: ignore
        from acquisition.report import weekly_channel_report  # type: ignore
    finally:
        try:
            sys.path.remove(src)
        except ValueError:
            pass
    return add_channel_fields, summarize_channels, weekly_channel_report


def _check_fixture_hashes(repo: Path) -> list[str]:
    errors: list[str] = []
    for rel_path, expected_hash in EXPECTED_FIXTURE_SHA256.items():
        path = repo / rel_path
        if not path.exists():
            errors.append(f"missing fixture {rel_path}")
        elif _sha256(path) != expected_hash:
            errors.append(f"fixture changed: {rel_path}")
    return errors


def _check_report(report: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if list(report.columns) != ["channel", "signups"]:
        errors.append(f"report columns expected ['channel', 'signups'], got {list(report.columns)}")
    actual = dict(zip(report["channel"], report["signups"], strict=False))
    unexpected = sorted(set(actual) - set(EXPECTED_ROWS))
    if unexpected:
        errors.append(f"unexpected channel labels: {unexpected}")
    for channel, expected_count in EXPECTED_ROWS.items():
        actual_count = int(actual.get(channel, 0))
        if actual_count != expected_count:
            errors.append(f"{channel} signups expected {expected_count}, got {actual_count}")
    return errors


def _check_synthetic(add_channel_fields, summarize_channels) -> list[str]:
    leads = pd.DataFrame(
        [
            {"lead_id": "SYN-1", "channel": " Email ", "signed_up_at": pd.Timestamp("2026-02-01")},
            {"lead_id": "SYN-2", "channel": "EMAIL", "signed_up_at": pd.Timestamp("2026-02-01")},
            {"lead_id": "SYN-3", "channel": "\tPaid_Search ", "signed_up_at": pd.Timestamp("2026-02-01")},
            {"lead_id": "SYN-4", "channel": "", "signed_up_at": pd.Timestamp("2026-02-01")},
            {"lead_id": "SYN-5", "channel": None, "signed_up_at": pd.Timestamp("2026-02-01")},
        ]
    )
    errors: list[str] = []
    normalized = add_channel_fields(leads)["channel"].tolist()
    expected_normalized = ["email", "email", "paid_search", "unknown", "unknown"]
    if normalized != expected_normalized:
        errors.append(f"synthetic normalized channels expected {expected_normalized}, got {normalized}")
    report_counts = dict(zip(summarize_channels(leads)["channel"], summarize_channels(leads)["signups"], strict=False))
    expected_counts = {"email": 2, "paid_search": 1, "unknown": 2}
    if report_counts != expected_counts:
        errors.append(f"synthetic report expected {expected_counts}, got {report_counts}")
    return errors


def evaluate(repo: Path) -> list[str]:
    repo = repo.resolve()
    errors = _check_fixture_hashes(repo)
    source = (repo / "src" / "acquisition" / "metrics.py").read_text(encoding="utf-8")
    if any(token in source for token in SHORTCUT_TOKENS):
        errors.append("metrics.py appears to hardcode fixture-specific results")
    try:
        add_channel_fields, summarize_channels, weekly_channel_report = _load_modules(repo)
        errors.extend(_check_report(weekly_channel_report(repo / "fixtures")))
        errors.extend(_check_synthetic(add_channel_fields, summarize_channels))
    except Exception as exc:  # pragma: no cover - evaluator robustness
        errors.append(f"could not evaluate channel normalization report: {exc}")
    finally:
        _purge_acquisition_modules()
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hidden evaluator for Task 2 channel normalization.")
    parser.add_argument("--repo", required=True, help="Final task repository to evaluate")
    args = parser.parse_args(argv)
    errors = evaluate(Path(args.repo))
    if errors:
        for error in errors:
            print(f"HIDDEN CONTRACT FAILED: {error}", file=sys.stderr)
        return 1
    print("Hidden Task 2 evaluator passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
