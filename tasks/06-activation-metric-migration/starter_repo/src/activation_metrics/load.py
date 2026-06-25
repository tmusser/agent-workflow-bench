from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_users(data_dir: Path) -> pd.DataFrame:
    users = pd.read_csv(Path(data_dir) / "users.csv")
    users["signup_at"] = pd.to_datetime(users["signup_at"], errors="coerce")
    if "cancelled_at" in users.columns:
        users["cancelled_at"] = pd.to_datetime(users["cancelled_at"], errors="coerce")
    if "is_test_account" in users.columns:
        users["is_test_account"] = users["is_test_account"].astype(str).str.strip().str.lower().eq("true")
    return users


def load_events(data_dir: Path) -> pd.DataFrame:
    events = pd.read_csv(Path(data_dir) / "events.csv")
    events["event_at"] = pd.to_datetime(events["event_at"], errors="coerce")
    return events
