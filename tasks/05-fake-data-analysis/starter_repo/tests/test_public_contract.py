from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_analysis_command_writes_public_outputs():
    out_dir = ROOT / "outputs"
    shutil.rmtree(out_dir, ignore_errors=True)

    subprocess.run([sys.executable, "scripts/reproduce_fake_lift.py"], cwd=ROOT, check=True)

    report_path = out_dir / "trust_report.json"
    summary_path = out_dir / "executive_summary.md"

    assert report_path.exists()
    assert summary_path.exists()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["dataset_path"].endswith("data/campaign_results.csv")
    assert isinstance(report["rows_total"], int)
    assert isinstance(report["causal_claim_allowed"], bool)
    assert isinstance(report["confident_lift_claim"], bool)
    assert isinstance(report["data_quality_blockers"], list)
    assert report["executive_summary_path"] == "outputs/executive_summary.md"
    assert report["trust_report_path"] == "outputs/trust_report.json"

    summary = summary_path.read_text(encoding="utf-8")
    assert summary.startswith("# Campaign Lift Summary")
