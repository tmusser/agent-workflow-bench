from __future__ import annotations

from pathlib import Path

import pandas as pd


def fixture_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "fixtures"


def load_tickets(path: str | Path) -> pd.DataFrame:
    tickets = pd.read_csv(path)
    tickets["created_at"] = pd.to_datetime(tickets["created_at"])
    tickets["first_response_at"] = pd.to_datetime(tickets["first_response_at"])
    return tickets
