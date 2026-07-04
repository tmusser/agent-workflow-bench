from __future__ import annotations

import pandas as pd


def add_channel_fields(leads: pd.DataFrame) -> pd.DataFrame:
    """Add normalized acquisition-channel fields to lead rows."""
    result = leads.copy()

    # BUG: this lowercases labels but leaves whitespace and missing labels unhandled.
    result["channel"] = result["channel"].str.lower()
    return result


def summarize_channels(leads: pd.DataFrame) -> pd.DataFrame:
    enriched = add_channel_fields(leads)
    grouped = (
        enriched.groupby("channel", sort=True)
        .agg(signups=("lead_id", "nunique"))
        .reset_index()
    )
    grouped["signups"] = grouped["signups"].astype(int)
    return grouped[["channel", "signups"]]
