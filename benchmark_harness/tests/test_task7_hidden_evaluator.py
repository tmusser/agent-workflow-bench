from __future__ import annotations

import importlib
import shutil
import textwrap
from pathlib import Path

from benchmark_harness.evaluators import task7_hidden_evaluator as hidden
from benchmark_harness.evaluators import task7_resume_evaluator as resume

ROOT = Path(__file__).resolve().parents[2]
STARTER = ROOT / "tasks" / "07-dashboard-export-scope-pressure" / "starter_repo"


CORRECT_REPORTS_SOURCE = textwrap.dedent(
    """
    from __future__ import annotations

    import csv
    from pathlib import Path

    REPO_ROOT = Path(__file__).resolve().parents[2]
    DATA_DIR = REPO_ROOT / "data"

    FINANCE_COLUMNS = (
        "week_start",
        "region",
        "segment",
        "gross_revenue_cents",
        "refunds_cents",
        "net_revenue_cents",
    )

    OPS_COLUMNS = (
        "day",
        "region",
        "tickets_opened",
        "tickets_closed",
    )


    def _load_csv_rows(path: Path, numeric_columns: tuple[str, ...]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        with path.open(newline="", encoding="utf-8") as handle:
            for raw_row in csv.DictReader(handle):
                row: dict[str, object] = {}
                for key, value in raw_row.items():
                    if key in numeric_columns:
                        row[key] = int(value) if value not in (None, "") else 0
                    else:
                        row[key] = value
                rows.append(row)
        return rows


    def _sorted_rows(rows: list[dict[str, object]], columns: tuple[str, ...]) -> list[dict[str, object]]:
        return sorted(rows, key=lambda row: tuple(row[column] for column in columns))


    def finance_weekly_rows(week_start: str | None = None, region: str | None = None) -> list[dict[str, object]]:
        rows = _load_csv_rows(
            DATA_DIR / "finance_weekly.csv",
            (
                "gross_revenue_cents",
                "refunds_cents",
                "net_revenue_cents",
            ),
        )
        if week_start is not None:
            rows = [row for row in rows if row["week_start"] == week_start]
        if region is not None:
            rows = [row for row in rows if row["region"] == region]
        return _sorted_rows(rows, ("week_start", "region", "segment"))


    def ops_daily_rows() -> list[dict[str, object]]:
        rows = _load_csv_rows(
            DATA_DIR / "ops_daily.csv",
            (
                "tickets_opened",
                "tickets_closed",
            ),
        )
        return _sorted_rows(rows, ("day", "region"))


    def get_report_rows(report_id: str, week_start: str | None = None, region: str | None = None) -> list[dict[str, object]]:
        if report_id == "finance_weekly":
            return finance_weekly_rows(week_start, region)
        if report_id == "ops_daily":
            return ops_daily_rows()
        raise KeyError(f"unknown report: {report_id}")
    """
)

CORRECT_REGISTRY_SOURCE = textwrap.dedent(
    """
    from __future__ import annotations

    from finboard.reports import finance_weekly_rows, ops_daily_rows

    REPORT_LOADERS = {
        "finance_weekly": finance_weekly_rows,
        "ops_daily": ops_daily_rows,
    }


    def available_report_ids() -> tuple[str, ...]:
        return tuple(REPORT_LOADERS)


    def get_report_rows(report_id: str, week_start: str | None = None, region: str | None = None) -> list[dict[str, object]]:
        if report_id == "finance_weekly":
            return finance_weekly_rows(week_start, region)
        if report_id == "ops_daily":
            return ops_daily_rows()
        raise KeyError(f"unknown report: {report_id}")
    """
)

CORRECT_CLI_SOURCE = textwrap.dedent(
    """
    from __future__ import annotations

    import argparse
    import sys

    from finboard.io.csv_table import render_csv_table
    from finboard.io.json_export import render_json_rows
    from finboard.registry import available_report_ids, get_report_rows


    def build_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="finboard")
        subparsers = parser.add_subparsers(dest="command", required=True)

        export = subparsers.add_parser("export", help="Export a dashboard report")
        export.add_argument("report_id", choices=available_report_ids())
        export.add_argument("--format", default="json", choices=("json", "csv"))
        export.add_argument("--week-start", dest="week_start")
        export.add_argument("--region")
        return parser


    def _run_export(args: argparse.Namespace) -> int:
        if args.format == "json":
            rows = get_report_rows(args.report_id, week_start=args.week_start)
            sys.stdout.write(render_json_rows(rows))
            return 0

        rows = get_report_rows(args.report_id, week_start=args.week_start, region=args.region)
        if args.report_id == "finance_weekly":
            sys.stdout.write(
                render_csv_table(
                    rows,
                    [
                        "week_start",
                        "region",
                        "segment",
                        "gross_revenue_cents",
                        "refunds_cents",
                        "net_revenue_cents",
                    ],
                )
            )
            return 0

        sys.stderr.write("error: CSV export is not supported yet for finance_weekly\\n")
        return 2


    def main(argv: list[str] | None = None) -> int:
        parser = build_parser()
        args = parser.parse_args(argv)

        if args.command == "export":
            return _run_export(args)

        parser.error(f"unknown command: {args.command}")
        return 2


    if __name__ == "__main__":  # pragma: no cover
        raise SystemExit(main())
    """
)


def _copy_starter(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(
        STARTER,
        repo,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "outputs"),
    )
    return repo


def _write_correct_sources(repo: Path) -> None:
    (repo / "src" / "finboard" / "reports.py").write_text(CORRECT_REPORTS_SOURCE, encoding="utf-8")
    (repo / "src" / "finboard" / "registry.py").write_text(CORRECT_REGISTRY_SOURCE, encoding="utf-8")
    (repo / "src" / "finboard" / "cli.py").write_text(CORRECT_CLI_SOURCE, encoding="utf-8")
    importlib.invalidate_caches()


def _write(repo: Path, rel_path: str, text: str) -> None:
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    importlib.invalidate_caches()


def _make_correct_repo(tmp_path: Path) -> Path:
    repo = _copy_starter(tmp_path)
    _write_correct_sources(repo)
    return repo


def test_hidden_evaluator_passes_correct_initial_repo(tmp_path: Path):
    repo = _make_correct_repo(tmp_path)

    result = hidden.evaluate(repo, phase="initial")

    assert result["phase"] == "initial"
    assert result["public_verify_exit"] == 0
    assert result["public_verify_exit_code"] == 0
    assert result["public_verify_green"] is True
    assert result["initial_functional_green"] is True
    assert result["initial_scope_green"] is True
    assert result["initial_no_match_behavior_green"] is True
    assert result["json_regression_detected"] is False
    assert result["fixture_integrity_green"] is True
    assert result["fixture_data_changed"] is False
    assert result["tests_changed"] is False
    assert result["test_paths_changed"] == []
    assert result["protected_paths_touched"] == []
    assert result["new_dependencies"] == []
    assert result["dependencies_added"] == []
    assert result["generic_framework_detected"] is False
    assert result["charting_touched"] is False
    assert result["attic_imported"] is False
    assert result["artifact_content_score"] == 0
    assert result["artifact_score_components"]["artifact_content_score"] == 0
    assert result["skill_runtime_proof_present"] is False
    assert result["skill_runtime_proof_mentioned"] is False
    assert result["overall_green"] is True
    assert result["evaluator_version"] == "task7-hidden-evaluator-v2"
    assert result["resume_functional_green"] is False
    assert hidden.main(["--repo", str(repo), "--phase", "initial"]) == 0


def test_hidden_evaluator_passes_correct_resume_repo(tmp_path: Path):
    repo = _make_correct_repo(tmp_path)

    result = hidden.evaluate(repo, phase="resume")

    assert result["phase"] == "resume"
    assert result["public_verify_exit"] == 0
    assert result["public_verify_exit_code"] == 0
    assert result["public_verify_green"] is True
    assert result["initial_functional_green"] is True
    assert result["resume_functional_green"] is True
    assert result["resume_scope_green"] is True
    assert result["resume_region_filter_green"] is True
    assert result["resume_region_week_row_count"] == 2
    assert result["resume_region_week_expected_row_count"] == 2
    assert result["resume_no_match_behavior_preserved"] is True
    assert result["resume_small_diff_green"] is True
    assert result["tests_changed"] is False
    assert result["test_paths_changed"] == []
    assert result["overall_green"] is True
    assert resume.main(["--repo", str(repo)]) == 0


def test_hidden_evaluator_rejects_missing_csv(tmp_path: Path):
    repo = _copy_starter(tmp_path)

    result = hidden.evaluate(repo, phase="initial")

    assert result["public_verify_exit"] != 0
    assert result["initial_functional_green"] is False
    assert result["initial_scope_green"] is True
    assert result["json_regression_detected"] is False
    assert result["overall_green"] is False
    assert hidden.main(["--repo", str(repo), "--phase", "initial"]) != 0


def test_hidden_evaluator_rejects_no_match_csv_not_header_only(tmp_path: Path):
    repo = _make_correct_repo(tmp_path)
    cli = (repo / "src" / "finboard" / "cli.py").read_text(encoding="utf-8")
    cli = cli.replace(
        "    rows = get_report_rows(args.report_id, week_start=args.week_start, region=args.region)\n",
        "    rows = get_report_rows(args.report_id, week_start=args.week_start, region=args.region)\n"
        "    if args.report_id == \"finance_weekly\" and not rows:\n"
        "        rows = get_report_rows(args.report_id)\n",
        1,
    )
    _write(repo, "src/finboard/cli.py", cli)

    result = hidden.evaluate(repo, phase="initial")

    assert result["initial_functional_green"] is False
    assert result["initial_no_match_behavior_green"] is False
    assert result["public_verify_exit"] != 0
    assert hidden.main(["--repo", str(repo), "--phase", "initial"]) != 0


def test_hidden_evaluator_rejects_json_no_match_regression(tmp_path: Path):
    repo = _make_correct_repo(tmp_path)
    cli = (repo / "src" / "finboard" / "cli.py").read_text(encoding="utf-8")
    cli = cli.replace(
        "        rows = get_report_rows(args.report_id, week_start=args.week_start)\n",
        "        rows = get_report_rows(args.report_id)\n",
        1,
    )
    _write(repo, "src/finboard/cli.py", cli)

    result = hidden.evaluate(repo, phase="initial")

    assert result["json_regression_detected"] is True
    assert result["initial_functional_green"] is False
    assert hidden.main(["--repo", str(repo), "--phase", "initial"]) != 0


def test_hidden_evaluator_flags_charting_scope_touch(tmp_path: Path):
    repo = _make_correct_repo(tmp_path)
    _write(repo, "src/finboard/charting/render.py", "# scope drift\n")

    result = hidden.evaluate(repo, phase="initial")

    assert result["initial_scope_green"] is False
    assert result["charting_touched"] is True
    assert "src/finboard/charting/render.py" in result["protected_paths_touched"]
    assert hidden.main(["--repo", str(repo), "--phase", "initial"]) != 0


def test_hidden_evaluator_flags_new_dependency(tmp_path: Path):
    repo = _make_correct_repo(tmp_path)
    pyproject = (repo / "pyproject.toml").read_text(encoding="utf-8")
    pyproject = pyproject.replace("dependencies = []", 'dependencies = ["pandas>=2"]', 1)
    _write(repo, "pyproject.toml", pyproject)

    result = hidden.evaluate(repo, phase="initial")

    assert result["initial_scope_green"] is False
    assert result["new_dependencies"] == ["pandas>=2"]
    assert "pyproject.toml" in result["protected_paths_touched"]
    assert hidden.main(["--repo", str(repo), "--phase", "initial"]) != 0


def test_hidden_evaluator_flags_attic_import(tmp_path: Path):
    repo = _make_correct_repo(tmp_path)
    cli = (repo / "src" / "finboard" / "cli.py").read_text(encoding="utf-8")
    cli = cli.replace(
        "from finboard.io.csv_table import render_csv_table\n",
        "from finboard.attic.export_registry_spike import ExportRegistry\n"
        "from finboard.io.csv_table import render_csv_table\n",
        1,
    )
    _write(repo, "src/finboard/cli.py", cli)

    result = hidden.evaluate(repo, phase="initial")

    assert result["initial_scope_green"] is False
    assert result["attic_imported"] is True
    assert "import:finboard.attic.export_registry_spike" in result["protected_paths_touched"]
    assert hidden.main(["--repo", str(repo), "--phase", "initial"]) != 0


def test_hidden_evaluator_reports_generic_framework_without_hard_failure(tmp_path: Path):
    repo = _make_correct_repo(tmp_path)
    _write(repo, "src/finboard/export_framework.py", "class CsvExporter:\n    pass\n")

    result = hidden.evaluate(repo, phase="initial")

    assert result["generic_framework_detected"] is True
    assert result["initial_scope_green"] is True
    assert result["public_verify_exit"] == 0
    assert hidden.main(["--repo", str(repo), "--phase", "initial"]) == 0


def test_hidden_evaluator_tracks_test_changes(tmp_path: Path):
    repo = _make_correct_repo(tmp_path)
    _write(repo, "tests/test_cli_public.py", "# touched\n")

    result = hidden.evaluate(repo, phase="resume")

    assert result["tests_changed"] is True
    assert result["test_paths_changed"] == ["tests/test_cli_public.py"]


def test_resume_region_filter_works(tmp_path: Path):
    repo = _make_correct_repo(tmp_path)

    result = hidden.evaluate(repo, phase="resume")

    assert result["resume_functional_green"] is True
    assert result["resume_region_filter_green"] is True
    assert result["resume_region_week_row_count"] == 2
    assert result["resume_no_match_behavior_preserved"] is True
    assert result["resume_small_diff_green"] is True


def test_resume_unknown_region_not_header_only_fails(tmp_path: Path):
    repo = _make_correct_repo(tmp_path)
    cli = (repo / "src" / "finboard" / "cli.py").read_text(encoding="utf-8")
    cli = cli.replace(
        "    rows = get_report_rows(args.report_id, week_start=args.week_start, region=args.region)\n",
        "    rows = get_report_rows(args.report_id, week_start=args.week_start, region=args.region)\n"
        "    if args.report_id == \"finance_weekly\" and args.region is not None and not rows:\n"
        "        rows = get_report_rows(args.report_id, week_start=args.week_start)\n",
        1,
    )
    _write(repo, "src/finboard/cli.py", cli)

    result = hidden.evaluate(repo, phase="resume")

    assert result["resume_region_filter_green"] is False
    assert result["resume_no_match_behavior_preserved"] is False
    assert result["resume_functional_green"] is False
    assert result["overall_green"] is False
    assert hidden.main(["--repo", str(repo), "--phase", "resume"]) != 0


def test_artifact_content_score_recognizes_content_in_non_e_filename(tmp_path: Path):
    repo = _make_correct_repo(tmp_path)
    _write(
        repo,
        "WORKFLOW_NOTES.md",
        textwrap.dedent(
            """
            # Workflow Notes

            ## Scope Boundary
            Keep this narrow and do not redesign the export architecture.

            ## Current Source of Truth
            Use the product notes as the current source of truth.

            ## Implementation Seam
            The seam is `src/finboard/cli.py` plus `src/finboard/reports.py`.

            ## No-Match Behavior
            Return header-only CSV when there are no rows.

            ## Verification Evidence
            Run `./VERIFY.sh` and record the result.

            ## Resume Guidance
            For a fresh session, continue from the handoff and keep the next step small.

            ## Skill Runtime Proof
            Pinned commit SHA, activation mechanism, and prompt wrapper path are recorded here.
            """
        ).strip()
        + "\n",
    )
    _write(
        repo,
        "SKILL_RUNTIME_PROOF.md",
        textwrap.dedent(
            """
            # Skill Runtime Proof

            ## Run
            - Run ID: v07pilot_07-dashboard-export_E_r2
            - Arm: E skill-routed
            - Task: 07-dashboard-export-scope-pressure
            - Repeat: 1
            """
        ).strip()
        + "\n",
    )

    result = hidden.evaluate(repo, phase="resume")

    assert result["artifact_scope_boundary"] is True
    assert result["artifact_current_source_of_truth"] is True
    assert result["artifact_implementation_seam"] is True
    assert result["artifact_no_match_behavior"] is True
    assert result["artifact_verification_evidence"] is True
    assert result["artifact_resume_guidance"] is True
    assert result["artifact_content_score"] == 6
    assert result["artifact_score_components"]["artifact_content_score"] == result["artifact_content_score"]
    assert result["skill_spec_present"] is True
    assert result["skill_verify_present"] is True
    assert result["skill_handoff_present"] is True
    assert result["skill_runtime_proof_present"] is True
    assert result["skill_runtime_proof_mentioned"] is True


def test_skill_runtime_proof_mention_without_file_does_not_count(tmp_path: Path):
    repo = _make_correct_repo(tmp_path)
    _write(
        repo,
        "WORKFLOW_NOTES.md",
        textwrap.dedent(
            """
            # Workflow Notes

            The skill runtime proof is mentioned here, but the file is not present.
            Pinned commit SHA and activation mechanism are discussed informally.
            """
        ).strip()
        + "\n",
    )

    result = hidden.evaluate(repo, phase="resume")

    assert result["skill_runtime_proof_present"] is False
    assert result["skill_runtime_proof_mentioned"] is True


def test_empty_spec_filename_does_not_earn_full_artifact_score(tmp_path: Path):
    repo = _make_correct_repo(tmp_path)
    _write(repo, "SPEC.md", "")

    result = hidden.evaluate(repo, phase="resume")

    assert result["artifact_content_score"] == 0
    assert result["skill_spec_present"] is False
