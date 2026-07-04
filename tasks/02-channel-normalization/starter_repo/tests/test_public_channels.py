from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acquisition.metrics import add_channel_fields, summarize_channels  # noqa: E402


def test_channel_labels_are_trimmed_and_lowercased():
    leads = pd.DataFrame(
        [
            {"lead_id": "PUBLIC-1", "channel": " Email ", "signed_up_at": pd.Timestamp("2026-02-01")},
            {"lead_id": "PUBLIC-2", "channel": "email", "signed_up_at": pd.Timestamp("2026-02-01")},
        ]
    )

    report = summarize_channels(leads)

    assert report.to_dict(orient="records") == [{"channel": "email", "signups": 2}]


def test_blank_channel_becomes_unknown():
    leads = pd.DataFrame(
        [
            {"lead_id": "PUBLIC-3", "channel": "", "signed_up_at": pd.Timestamp("2026-02-01")},
            {"lead_id": "PUBLIC-4", "channel": None, "signed_up_at": pd.Timestamp("2026-02-01")},
        ]
    )

    enriched = add_channel_fields(leads)

    assert enriched["channel"].tolist() == ["unknown", "unknown"]


def test_report_keeps_existing_columns_and_sorted_channel_order():
    leads = pd.DataFrame(
        [
            {"lead_id": "PUBLIC-5", "channel": "Referral", "signed_up_at": pd.Timestamp("2026-02-01")},
            {"lead_id": "PUBLIC-6", "channel": "Email", "signed_up_at": pd.Timestamp("2026-02-01")},
        ]
    )

    report = summarize_channels(leads)

    assert list(report.columns) == ["channel", "signups"]
    assert report["channel"].tolist() == ["email", "referral"]
