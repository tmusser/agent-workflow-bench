from __future__ import annotations

from pathlib import Path

import pandas as pd


def fixture_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "fixtures"


def load_orders(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def load_refund_events(path: str | Path) -> pd.DataFrame:
    refunds = pd.read_csv(path)
    refunds["refunded_at"] = pd.to_datetime(refunds["refunded_at"])
    return refunds
