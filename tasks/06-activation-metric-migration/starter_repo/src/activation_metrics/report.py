from __future__ import annotations

from pathlib import Path

import pandas as pd

from .activation import REPORT_COLUMNS, compute_activation_rate_v1, compute_activation_rate_v2


def build_activation_report(users: pd.DataFrame, events: pd.DataFrame, month: str, definition: str) -> pd.DataFrame:
    if definition == "v1":
        row = compute_activation_rate_v1(users, events, month)
    elif definition == "v2":
        row = compute_activation_rate_v2(users, events, month)
    else:
        raise ValueError(f"unknown definition: {definition}")
    return pd.DataFrame([row], columns=REPORT_COLUMNS)


def write_activation_report(data_dir: Path, definition_version: str, month: str, out_path: Path) -> Path:
    from .load import load_events, load_users

    users = load_users(data_dir)
    events = load_events(data_dir)
    report = build_activation_report(users, events, month, definition_version)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(out_path, index=False)
    return out_path
