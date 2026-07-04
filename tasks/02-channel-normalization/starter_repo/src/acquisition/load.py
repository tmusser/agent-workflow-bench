from __future__ import annotations

from pathlib import Path

import pandas as pd


def fixture_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "fixtures"


def load_leads(path: str | Path) -> pd.DataFrame:
    leads = pd.read_csv(path)
    leads["signed_up_at"] = pd.to_datetime(leads["signed_up_at"])
    return leads
