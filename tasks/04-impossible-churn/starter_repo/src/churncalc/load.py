from __future__ import annotations

from pathlib import Path

import pandas as pd


def fixture_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "fixtures"


def load_plan_history(path: str | Path | None = None) -> pd.DataFrame:
    path = Path(path) if path is not None else fixture_dir() / "plan_history.csv"
    df = pd.read_csv(path)
    df["valid_from"] = pd.to_datetime(df["valid_from"])
    df["valid_to"] = pd.to_datetime(df["valid_to"], errors="coerce")
    return df


def load_cancellation_events(path: str | Path | None = None) -> pd.DataFrame:
    path = Path(path) if path is not None else fixture_dir() / "cancellation_events.csv"
    df = pd.read_csv(path)
    df["cancelled_at"] = pd.to_datetime(df["cancelled_at"])
    return df
