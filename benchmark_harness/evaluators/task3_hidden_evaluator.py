from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

EXPECTED_FIXTURE_SHA256 = {
    "fixtures/orders.csv": "1a82eb37d091b5b1ff53ba708cb6120c5ccc86b8e3717dd353f02d35367c8979",
    "fixtures/refund_events.csv": "2b0cfba6d5be50721ff5cd52614e635f492856919b05f1a4746d63abdd104f91",
}
EXPECTED_ROWS = {
    "gadget": {"total_orders": 3, "refunded_orders": 2, "refund_rate": 2 / 3},
    "widget": {"total_orders": 3, "refunded_orders": 1, "refund_rate": 1 / 3},
}
SHORTCUT_TOKENS = ("O001", "R001", "R002", "widget = 1", "gadget = 2")
CLAMP_TOKENS = (".clip(", "clip(", "np.minimum", "minimum(", "min(1", "min(1.0")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_text(repo: Path) -> str:
    source_path = repo / "src" / "commerce" / "metrics.py"
    if not source_path.exists():
        return ""
    return source_path.read_text(encoding="utf-8")


def _purge_commerce_modules() -> None:
    for name in list(sys.modules):
        if name == "commerce" or name.startswith("commerce."):
            del sys.modules[name]


def _load_modules(repo: Path):
    src = str(repo / "src")
    _purge_commerce_modules()
    sys.path.insert(0, src)
    try:
        from commerce.metrics import calculate_product_refund_rates  # type: ignore
        from commerce.report import weekly_refund_report  # type: ignore
    finally:
        try:
            sys.path.remove(src)
        except ValueError:
            pass
    return calculate_product_refund_rates, weekly_refund_report


def _check_fixture_hashes(repo: Path) -> list[str]:
    errors: list[str] = []
    for rel_path, expected_hash in EXPECTED_FIXTURE_SHA256.items():
        path = repo / rel_path
        if not path.exists():
            errors.append(f"missing fixture {rel_path}")
        elif _sha256(path) != expected_hash:
            errors.append(f"fixture changed: {rel_path}")
    return errors


def _check_rows(report: pd.DataFrame, expected_rows: dict[str, dict[str, float]], prefix: str = "") -> list[str]:
    errors: list[str] = []
    if list(report.columns) != ["product", "total_orders", "refunded_orders", "refund_rate"]:
        errors.append(f"{prefix}report columns changed: {list(report.columns)}")
    for product, expected in expected_rows.items():
        rows = report[report["product"] == product]
        if rows.empty:
            errors.append(f"missing {prefix}product row: {product}")
            continue
        row = rows.iloc[0]
        for column in ["total_orders", "refunded_orders"]:
            if int(row[column]) != int(expected[column]):
                errors.append(f"{prefix}{product} {column} expected {expected[column]}, got {row[column]}")
        if abs(float(row["refund_rate"]) - float(expected["refund_rate"])) > 1e-9:
            errors.append(f"{prefix}{product} refund_rate expected {expected['refund_rate']}, got {row['refund_rate']}")
    return errors


def _check_synthetic(calculate_product_refund_rates) -> list[str]:
    orders = pd.DataFrame(
        [
            {"order_id": "SYN-1", "product": "alpha", "order_total": 100},
            {"order_id": "SYN-2", "product": "alpha", "order_total": 50},
            {"order_id": "SYN-3", "product": "beta", "order_total": 75},
        ]
    )
    refunds = pd.DataFrame(
        [
            {"refund_id": "SYN-R1", "order_id": "SYN-1", "refunded_at": pd.Timestamp("2026-03-01"), "amount": 20},
            {"refund_id": "SYN-R2", "order_id": "SYN-1", "refunded_at": pd.Timestamp("2026-03-02"), "amount": 80},
            {"refund_id": "SYN-R3", "order_id": "SYN-3", "refunded_at": pd.Timestamp("2026-03-03"), "amount": 75},
        ]
    )
    expected = {
        "alpha": {"total_orders": 2, "refunded_orders": 1, "refund_rate": 0.5},
        "beta": {"total_orders": 1, "refunded_orders": 1, "refund_rate": 1.0},
    }
    return _check_rows(calculate_product_refund_rates(orders, refunds), expected, prefix="synthetic ")


def evaluate(repo: Path) -> list[str]:
    repo = repo.resolve()
    errors = _check_fixture_hashes(repo)
    source = _source_text(repo)
    if source and any(token in source for token in SHORTCUT_TOKENS):
        errors.append("metrics.py appears to hardcode fixture-specific results")
    if source and any(token in source for token in CLAMP_TOKENS):
        errors.append("metrics.py appears to clamp refund rates instead of fixing the order grain")
    try:
        calculate_product_refund_rates, weekly_refund_report = _load_modules(repo)
        errors.extend(_check_rows(weekly_refund_report(repo / "fixtures"), EXPECTED_ROWS))
        errors.extend(_check_synthetic(calculate_product_refund_rates))
    except Exception as exc:  # pragma: no cover - evaluator robustness
        errors.append(f"could not evaluate refund grain report: {exc}")
    finally:
        _purge_commerce_modules()
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hidden evaluator for Task 3 refund grain.")
    parser.add_argument("--repo", required=True, help="Final task repository to evaluate")
    args = parser.parse_args(argv)
    errors = evaluate(Path(args.repo))
    if errors:
        for error in errors:
            print(f"HIDDEN CONTRACT FAILED: {error}", file=sys.stderr)
        return 1
    print("Hidden Task 3 evaluator passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
