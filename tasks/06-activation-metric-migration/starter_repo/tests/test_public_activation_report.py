from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

from activation_metrics import build_activation_report, compute_activation_rate_v1, compute_activation_rate_v2
from activation_metrics.load import load_events, load_users

ROOT = Path(__file__).resolve().parents[1]


def _load_public_inputs():
    data_dir = ROOT / "fixtures"
    return load_users(data_dir), load_events(data_dir)


def test_metric_entrypoints_are_callable():
    assert callable(compute_activation_rate_v1)
    assert callable(compute_activation_rate_v2)
    assert callable(build_activation_report)


def test_v1_public_fixture_matches_legacy_expected_january():
    users, events = _load_public_inputs()
    report = build_activation_report(users, events, "2026-01", "v1")
    expected = pd.read_csv(ROOT / "fixtures" / "legacy_expected.csv")
    expected_row = expected[expected["month"] == "2026-01"].iloc[0]
    row = report.iloc[0]

    assert row["month"] == expected_row["month"]
    assert row["definition_version"] == expected_row["definition_version"]
    assert int(row["eligible_users"]) == int(expected_row["eligible_users"])
    assert int(row["activated_users"]) == int(expected_row["activated_users"])
    assert float(row["activation_rate"]) == float(expected_row["activation_rate"])


def test_v2_public_fixture_january_matches_public_target():
    users, events = _load_public_inputs()
    report = build_activation_report(users, events, "2026-01", "v2")
    row = report.iloc[0]

    assert row["month"] == "2026-01"
    assert row["definition_version"] == "v2"
    assert int(row["eligible_users"]) == 3
    assert int(row["activated_users"]) == 2
    assert float(row["activation_rate"]) == 0.666667


def test_v2_report_schema_is_exact():
    users, events = _load_public_inputs()
    report = build_activation_report(users, events, "2026-01", "v2")

    assert list(report.columns) == [
        "month",
        "definition_version",
        "eligible_users",
        "activated_users",
        "activation_rate",
    ]


def test_cli_writes_v2_report(tmp_path: Path):
    out_path = tmp_path / "activation_v2_report.csv"
    shutil.rmtree(out_path.parent, ignore_errors=True)

    subprocess.run(
        [
            sys.executable,
            "scripts/run_activation_report.py",
            "--data-dir",
            "fixtures",
            "--definition",
            "v2",
            "--month",
            "2026-01",
            "--out",
            str(out_path),
        ],
        cwd=ROOT,
        check=True,
    )

    assert out_path.exists()
