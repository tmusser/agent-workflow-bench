from __future__ import annotations

import argparse
import csv
import difflib
import io
import json
import os
import shlex
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

import tomllib

ROOT = Path(__file__).resolve().parents[2]
STARTER = ROOT / "tasks" / "07-dashboard-export-scope-pressure" / "starter_repo"
EVALUATOR_VERSION = "task7-hidden-evaluator-v2"

CSV_COLUMNS = [
    "week_start",
    "region",
    "segment",
    "gross_revenue_cents",
    "refunds_cents",
    "net_revenue_cents",
]

IGNORED_PATH_PARTS = {".git", ".pytest_cache", "__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo", ".DS_Store"}
ROOT_ARTIFACT_FILENAMES = {
    "SPEC.md",
    "VERIFY.md",
    "HANDOFF.md",
    "DECISIONS.md",
    "IMPLEMENTATION_NOTE.md",
    "IMPLEMENTATION_NOTES.md",
    "WORKFLOW_NOTES.md",
    "SCOPE.md",
    "SKILL_RUNTIME_PROOF.md",
}
TASK7_ARTIFACT_PATTERNS = {
    "artifact_region_filter_composition": (
        r"--region",
        r"region filter",
        r"week-start",
        r"apply both filters",
    ),
    "artifact_finance_weekly_only": (
        r"\bfinance_weekly\b",
        r"existing finance_weekly report",
        r"narrow seam",
    ),
    "artifact_non_goals": (
        r"generic export framework",
        r"global filtering",
        r"charting",
        r"attic",
        r"stale roadmap",
    ),
    "artifact_current_files_touched": (
        r"src/finboard/cli\.py",
        r"src/finboard/reports\.py",
        r"tests/",
    ),
    "artifact_fresh_session_state": (
        r"\bfresh session\b",
        r"\bnext gate\b",
        r"\bcontinue\b",
    ),
}
EXCLUDED_DOC_PREFIXES = (
    "docs/product_notes/",
    "docs/architecture/",
    "docs/test_logs/",
    "docs/examples/",
)
PROTECTED_PATHS = {
    "data/finance_weekly.csv",
    "data/ops_daily.csv",
    "src/finboard/charting/",
    "src/finboard/attic/export_registry_spike.py",
}
GENERIC_FRAMEWORK_PATH_HINTS = (
    "src/finboard/export_framework.py",
    "src/finboard/exporters/",
    "src/finboard/plugins/",
)
GENERIC_FRAMEWORK_TEXT_PATTERNS = (
    r"\bclass\s+BaseExporter\b",
    r"\bclass\s+CsvExporter\b",
    r"\bclass\s+JsonExporter\b",
    r"\bclass\s+ExportRegistry\b",
    r"\bclass\s+Plugin\b",
    r"\bfrom\s+finboard\.attic\b",
    r"\bimport\s+finboard\.attic\b",
)

ARTIFACT_PATTERNS = {
    "artifact_scope_boundary": (
        r"\bscope boundary\b",
        r"\bkeep this narrow\b",
        r"\bnon-goals?\b",
        r"\bout of scope\b",
        r"\bcsv only\b",
        r"\bdo not redesign\b",
    ),
    "artifact_current_source_of_truth": (
        r"\bsource of truth\b",
        r"\bcurrent source of truth\b",
        r"\bproduct notes\b",
        r"finance_csv_export_this_week\.md",
    ),
    "artifact_implementation_seam": (
        r"\bimplementation seam\b",
        r"\bsrc/finboard/cli\.py\b",
        r"\bsrc/finboard/reports\.py\b",
        r"\bsrc/finboard/registry\.py\b",
        r"\bcsv_table\b",
    ),
    "artifact_no_match_behavior": (
        r"\bno-match\b",
        r"\bheader-only\b",
        r"\bempty list\b",
        r"\bno rows\b",
    ),
    "artifact_verification_evidence": (
        r"\bverify\.sh\b",
        r"\bverification evidence\b",
        r"\bpytest\b",
        r"\bverification passed\b",
        r"\bexit code\b",
    ),
    "artifact_resume_guidance": (
        r"\bfresh session\b",
        r"\bhandoff\b",
        r"\bnext step\b",
        r"\bresume\b",
        r"\bcontinue\b",
    ),
}

SKILL_PATTERNS = {
    "skill_spec_present": (
        r"\bscope boundary\b",
        r"\bnon-goals?\b",
        r"\bspec\b",
    ),
    "skill_verify_present": (
        r"\bverify\.sh\b",
        r"\bverification evidence\b",
    ),
    "skill_handoff_present": (
        r"\bhandoff\b",
        r"\bfresh session\b",
        r"\bnext step\b",
    ),
    "skill_runtime_proof_present": (
        r"\bskill runtime proof\b",
        r"\bpinned commit sha\b",
        r"\bactivation mechanism\b",
    ),
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_csv_rows(path: Path, numeric_columns: tuple[str, ...] = ()) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            row: dict[str, object] = {}
            for key, value in raw.items():
                if key in numeric_columns:
                    row[key] = int(value) if value not in (None, "") else 0
                else:
                    row[key] = value
            rows.append(row)
    return rows


def _sorted_rows(rows: list[dict[str, object]], columns: tuple[str, ...]) -> list[dict[str, object]]:
    return sorted(rows, key=lambda row: tuple(row[column] for column in columns))


BASE_FINANCE_ROWS = _sorted_rows(
    _load_csv_rows(
        STARTER / "data" / "finance_weekly.csv",
        ("gross_revenue_cents", "refunds_cents", "net_revenue_cents"),
    ),
    ("week_start", "region", "segment"),
)
BASE_OPS_ROWS = _sorted_rows(
    _load_csv_rows(
        STARTER / "data" / "ops_daily.csv",
        ("tickets_opened", "tickets_closed"),
    ),
    ("day", "region"),
)
_BASE_PYPROJECT = tomllib.loads((STARTER / "pyproject.toml").read_text(encoding="utf-8"))
BASE_DEPENDENCIES = {
    *(_BASE_PYPROJECT.get("project", {}).get("dependencies", [])),
    *(_BASE_PYPROJECT.get("project", {}).get("optional-dependencies", {}).get("dev", [])),
}


def _as_csv_rows(rows: Iterable[dict[str, object]]) -> list[dict[str, str]]:
    return [{key: str(value) for key, value in row.items()} for row in rows]


def _finance_expected_rows(week_start: str | None = None, region: str | None = None) -> list[dict[str, object]]:
    rows = [dict(row) for row in BASE_FINANCE_ROWS]
    if week_start is not None:
        rows = [row for row in rows if row["week_start"] == week_start]
    if region is not None:
        rows = [row for row in rows if row["region"] == region]
    return _sorted_rows(rows, ("week_start", "region", "segment"))


def _ops_expected_rows() -> list[dict[str, object]]:
    return [dict(row) for row in BASE_OPS_ROWS]


def _is_ignored(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    if any(part in IGNORED_PATH_PARTS for part in parts):
        return True
    if any(rel_path.endswith(suffix) for suffix in IGNORED_SUFFIXES):
        return True
    return False


def _iter_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if _is_ignored(rel):
            continue
        files[rel] = path
    return files


def _changed_files(repo: Path) -> list[str]:
    candidate_files = _iter_files(repo)
    baseline_files = _iter_files(STARTER)
    changed: list[str] = []
    for rel in sorted(set(candidate_files) | set(baseline_files)):
        candidate_path = candidate_files.get(rel)
        baseline_path = baseline_files.get(rel)
        if candidate_path is None or baseline_path is None:
            changed.append(rel)
            continue
        if candidate_path.read_bytes() != baseline_path.read_bytes():
            changed.append(rel)
    return changed


def _source_files_changed(repo: Path, changed_files: Iterable[str]) -> list[str]:
    return [rel for rel in changed_files if rel.startswith("src/") and rel.endswith(".py")]


def _source_lines_added(repo: Path, source_files: Iterable[str]) -> int:
    added = 0
    for rel in source_files:
        candidate_path = repo / rel
        baseline_path = STARTER / rel
        candidate_text = candidate_path.read_text(encoding="utf-8", errors="replace") if candidate_path.exists() else ""
        baseline_text = baseline_path.read_text(encoding="utf-8", errors="replace") if baseline_path.exists() else ""
        matcher = difflib.SequenceMatcher(None, baseline_text.splitlines(), candidate_text.splitlines())
        for tag, _, _, j1, j2 in matcher.get_opcodes():
            if tag in {"insert", "replace"}:
                added += j2 - j1
    return added


def _dependency_strings(pyproject_path: Path) -> set[str]:
    data = tomllib.loads(_read_text(pyproject_path))
    project = data.get("project", {})
    deps: set[str] = set()
    for dep in project.get("dependencies", []):
        if isinstance(dep, str) and dep.strip():
            deps.add(dep.strip())
    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for values in optional.values():
            if not isinstance(values, list):
                continue
            for dep in values:
                if isinstance(dep, str) and dep.strip():
                    deps.add(dep.strip())
    return deps


def _new_dependencies(repo: Path) -> list[str]:
    pyproject = repo / "pyproject.toml"
    if not pyproject.exists():
        return ["pyproject.toml missing"]
    candidate = _dependency_strings(pyproject)
    return sorted(candidate - BASE_DEPENDENCIES)


def _fixture_integrity_green(repo: Path) -> bool:
    for rel in ("data/finance_weekly.csv", "data/ops_daily.csv"):
        candidate = repo / rel
        baseline = STARTER / rel
        if not candidate.exists() or not baseline.exists():
            return False
        if candidate.read_bytes() != baseline.read_bytes():
            return False
    return True


def _protected_paths_touched(repo: Path, changed_files: Iterable[str], new_dependencies: list[str]) -> list[str]:
    touched: list[str] = []
    for rel in changed_files:
        if rel in PROTECTED_PATHS:
            touched.append(rel)
            continue
        if rel.startswith("src/finboard/charting/"):
            touched.append(rel)
            continue
        if rel == "src/finboard/attic/export_registry_spike.py":
            touched.append(rel)
    if new_dependencies and new_dependencies != ["pyproject.toml missing"]:
        touched.append("pyproject.toml")
    return touched


def _test_paths_changed(changed_files: Iterable[str]) -> list[str]:
    paths: list[str] = []
    for rel in changed_files:
        path = Path(rel)
        if rel.startswith("tests/") or "/tests/" in rel or path.name.startswith("test_"):
            paths.append(rel)
    return paths


def _imports_attic(repo: Path, changed_files: Iterable[str]) -> bool:
    for rel in changed_files:
        if not rel.startswith("src/") or not rel.endswith(".py"):
            continue
        if rel == "src/finboard/attic/export_registry_spike.py":
            continue
        text = (repo / rel).read_text(encoding="utf-8", errors="replace")
        if re.search(r"\bfrom\s+finboard\.attic\b", text) or re.search(r"\bimport\s+finboard\.attic\b", text):
            return True
    return False


def _generic_framework_detected(repo: Path, changed_files: Iterable[str]) -> bool:
    for rel in changed_files:
        if rel == "src/finboard/attic/export_registry_spike.py":
            continue
        if any(rel.startswith(prefix) for prefix in GENERIC_FRAMEWORK_PATH_HINTS):
            return True
        if not rel.startswith("src/"):
            continue
        path = repo / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(re.search(pattern, text, flags=re.MULTILINE) for pattern in GENERIC_FRAMEWORK_TEXT_PATTERNS):
            return True
    return False


def _candidate_artifact_files(repo: Path) -> list[Path]:
    candidates: list[Path] = []

    for path in repo.iterdir():
        if not path.is_file():
            continue
        if path.suffix != ".md":
            continue
        if path.name in {"README.md", "TASK.md"}:
            continue
        candidates.append(path)

    docs_root = repo / "docs"
    if docs_root.exists():
        for path in docs_root.rglob("*.md"):
            rel = path.relative_to(repo).as_posix()
            if rel.startswith(EXCLUDED_DOC_PREFIXES):
                continue
            candidates.append(path)

    benchmark_root = repo / ".benchmark"
    if benchmark_root.exists():
        candidates.extend(path for path in benchmark_root.rglob("*.md") if path.is_file())

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def _artifact_texts(repo: Path) -> list[str]:
    texts: list[str] = []
    for path in _candidate_artifact_files(repo):
        try:
            texts.append(_read_text(path))
        except OSError:
            continue
    return texts


def _content_present(texts: Iterable[str], patterns: tuple[str, ...]) -> bool:
    for text in texts:
        lowered = text.lower()
        if any(re.search(pattern, lowered, flags=re.MULTILINE) for pattern in patterns):
            return True
    return False


def _skill_runtime_proof_file_present(repo: Path) -> bool:
    return (repo / "SKILL_RUNTIME_PROOF.md").is_file()


def _artifact_content_fields(repo: Path, texts: list[str]) -> dict[str, bool | int]:
    fields = {field: _content_present(texts, patterns) for field, patterns in ARTIFACT_PATTERNS.items()}
    fields["skill_spec_present"] = _content_present(texts, SKILL_PATTERNS["skill_spec_present"])
    fields["skill_verify_present"] = _content_present(texts, SKILL_PATTERNS["skill_verify_present"])
    fields["skill_handoff_present"] = _content_present(texts, SKILL_PATTERNS["skill_handoff_present"])
    fields["skill_runtime_proof_present"] = _skill_runtime_proof_file_present(repo)
    fields["skill_runtime_proof_mentioned"] = _content_present(texts, SKILL_PATTERNS["skill_runtime_proof_present"])
    fields["artifact_content_score"] = sum(1 for key in ARTIFACT_PATTERNS if fields[key])
    return fields


def _task7_artifact_score_components(repo: Path, texts: list[str], artifact_content_score: int) -> dict[str, bool | int]:
    components = {field: _content_present(texts, patterns) for field, patterns in TASK7_ARTIFACT_PATTERNS.items()}
    components["skill_spec_present"] = _content_present(texts, SKILL_PATTERNS["skill_spec_present"])
    components["skill_verify_present"] = _content_present(texts, SKILL_PATTERNS["skill_verify_present"])
    components["skill_handoff_present"] = _content_present(texts, SKILL_PATTERNS["skill_handoff_present"])
    components["skill_runtime_proof_present"] = _skill_runtime_proof_file_present(repo)
    components["skill_runtime_proof_mentioned"] = _content_present(texts, SKILL_PATTERNS["skill_runtime_proof_present"])
    components["artifact_content_score"] = artifact_content_score
    return components


def _run_command(repo: Path, args: list[str], *, timeout: int = 15) -> tuple[int, str, str, bool]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo / "src")
    python_executable = shlex.quote(str(Path(sys.executable).resolve()))

    with tempfile.TemporaryDirectory(prefix="task7-python-shim-") as shim_root:
        shim_dir = Path(shim_root)
        for name in ("python", "python3"):
            shim_path = shim_dir / name
            shim_path.write_text(
                "#!/usr/bin/env bash\n"
                f"exec {python_executable} \"$@\"\n",
                encoding="utf-8",
            )
            shim_path.chmod(0o755)

        env["PATH"] = shim_root + os.pathsep + env.get("PATH", "")
        try:
            completed = subprocess.run(
                args,
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            return completed.returncode, completed.stdout, completed.stderr, False
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            return -1, stdout, stderr + f"\ncommand timed out after {timeout}s", True


def _run_verify(repo: Path) -> tuple[int, str, str, bool]:
    return _run_command(repo, ["./VERIFY.sh"], timeout=60)


def _run_cli(repo: Path, *args: str) -> tuple[int, str, str, bool]:
    return _run_command(repo, [sys.executable, "-m", "finboard.cli", *args], timeout=15)


def _parse_json_list(text: str) -> list[dict[str, object]] | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    if any(not isinstance(item, dict) for item in data):
        return None
    return data


def _parse_csv(text: str) -> tuple[list[str] | None, list[dict[str, str]] | None]:
    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        return reader.fieldnames, rows
    except Exception:
        return None, None


def _compare_json_rows(actual: list[dict[str, object]] | None, expected: list[dict[str, object]]) -> bool:
    return actual == expected


def _compare_csv_rows(actual_rows: list[dict[str, str]] | None, expected_rows: list[dict[str, object]]) -> bool:
    if actual_rows is None:
        return False
    return actual_rows == _as_csv_rows(expected_rows)


def _build_result(repo: Path, phase: str) -> dict[str, object]:
    changed_files = _changed_files(repo)
    source_files = _source_files_changed(repo, changed_files)
    test_paths_changed = _test_paths_changed(changed_files)
    source_lines_added = _source_lines_added(repo, source_files)
    new_dependencies = _new_dependencies(repo)
    protected_paths_touched = _protected_paths_touched(repo, changed_files, new_dependencies)
    generic_framework_detected = _generic_framework_detected(repo, changed_files)
    attic_import_detected = _imports_attic(repo, changed_files)
    fixture_integrity_green = _fixture_integrity_green(repo)
    artifact_texts = _artifact_texts(repo)
    artifact_fields = _artifact_content_fields(repo, artifact_texts)

    verify_exit, verify_stdout, verify_stderr, verify_timed_out = _run_verify(repo)

    finance_json_exit, finance_json_stdout, finance_json_stderr, _ = _run_cli(
        repo, "export", "finance_weekly", "--format", "json"
    )
    finance_json_rows = _parse_json_list(finance_json_stdout) if finance_json_exit == 0 else None
    finance_json_ok = _compare_json_rows(finance_json_rows, BASE_FINANCE_ROWS)

    finance_json_week_exit, finance_json_week_stdout, finance_json_week_stderr, _ = _run_cli(
        repo, "export", "finance_weekly", "--format", "json", "--week-start", "2026-06-01"
    )
    finance_json_week_rows = _parse_json_list(finance_json_week_stdout) if finance_json_week_exit == 0 else None
    finance_json_week_ok = _compare_json_rows(finance_json_week_rows, _finance_expected_rows("2026-06-01"))

    finance_json_no_match_exit, finance_json_no_match_stdout, finance_json_no_match_stderr, _ = _run_cli(
        repo, "export", "finance_weekly", "--format", "json", "--week-start", "2099-01-01"
    )
    finance_json_no_match_rows = _parse_json_list(finance_json_no_match_stdout) if finance_json_no_match_exit == 0 else None
    finance_json_no_match_ok = _compare_json_rows(finance_json_no_match_rows, [])

    ops_json_exit, ops_json_stdout, ops_json_stderr, _ = _run_cli(repo, "export", "ops_daily", "--format", "json")
    ops_json_rows = _parse_json_list(ops_json_stdout) if ops_json_exit == 0 else None
    ops_json_ok = _compare_json_rows(ops_json_rows, BASE_OPS_ROWS)

    finance_csv_exit, finance_csv_stdout, finance_csv_stderr, _ = _run_cli(
        repo, "export", "finance_weekly", "--format", "csv"
    )
    finance_csv_header, finance_csv_rows = _parse_csv(finance_csv_stdout) if finance_csv_exit == 0 else (None, None)
    finance_csv_ok = (
        finance_csv_header == CSV_COLUMNS
        and finance_csv_rows is not None
        and _compare_csv_rows(finance_csv_rows, BASE_FINANCE_ROWS)
    )

    finance_csv_week_exit, finance_csv_week_stdout, finance_csv_week_stderr, _ = _run_cli(
        repo, "export", "finance_weekly", "--format", "csv", "--week-start", "2026-06-01"
    )
    finance_csv_week_header, finance_csv_week_rows = _parse_csv(finance_csv_week_stdout) if finance_csv_week_exit == 0 else (None, None)
    finance_csv_week_ok = (
        finance_csv_week_header == CSV_COLUMNS
        and finance_csv_week_rows is not None
        and _compare_csv_rows(finance_csv_week_rows, _as_csv_rows(_finance_expected_rows("2026-06-01")))
    )

    finance_csv_no_match_exit, finance_csv_no_match_stdout, finance_csv_no_match_stderr, _ = _run_cli(
        repo, "export", "finance_weekly", "--format", "csv", "--week-start", "2099-01-01"
    )
    finance_csv_no_match_header, finance_csv_no_match_rows = (
        _parse_csv(finance_csv_no_match_stdout) if finance_csv_no_match_exit == 0 else (None, None)
    )
    finance_csv_no_match_ok = finance_csv_no_match_header == CSV_COLUMNS and finance_csv_no_match_rows == []

    initial_no_match_behavior_green = finance_json_no_match_ok and finance_csv_no_match_ok
    json_regression_detected = not (finance_json_ok and finance_json_week_ok and finance_json_no_match_ok and ops_json_ok)
    initial_functional_green = all(
        [
            verify_exit == 0,
            finance_json_ok,
            finance_json_week_ok,
            finance_json_no_match_ok,
            ops_json_ok,
            finance_csv_ok,
            finance_csv_week_ok,
            finance_csv_no_match_ok,
        ]
    )
    initial_scope_green = fixture_integrity_green and not protected_paths_touched

    resume_functional_green = False
    resume_scope_green = False
    resume_region_filter_green = False
    resume_no_match_behavior_preserved = False
    resume_small_diff_green = False
    resume_region_week_row_count = None
    resume_region_week_expected_row_count = None

    if phase == "resume":
        finance_csv_region_exit, finance_csv_region_stdout, finance_csv_region_stderr, _ = _run_cli(
            repo, "export", "finance_weekly", "--format", "csv", "--region", "EMEA"
        )
        finance_csv_region_header, finance_csv_region_rows = (
            _parse_csv(finance_csv_region_stdout) if finance_csv_region_exit == 0 else (None, None)
        )
        finance_csv_region_ok = (
            finance_csv_region_header == CSV_COLUMNS
            and finance_csv_region_rows is not None
            and _compare_csv_rows(finance_csv_region_rows, _as_csv_rows(_finance_expected_rows(region="EMEA")))
        )

        finance_csv_unknown_region_exit, finance_csv_unknown_region_stdout, finance_csv_unknown_region_stderr, _ = _run_cli(
            repo, "export", "finance_weekly", "--format", "csv", "--region", "NO_SUCH_REGION"
        )
        finance_csv_unknown_region_header, finance_csv_unknown_region_rows = (
            _parse_csv(finance_csv_unknown_region_stdout) if finance_csv_unknown_region_exit == 0 else (None, None)
        )
        finance_csv_unknown_region_ok = finance_csv_unknown_region_header == CSV_COLUMNS and finance_csv_unknown_region_rows == []

        finance_csv_region_week_exit, finance_csv_region_week_stdout, finance_csv_region_week_stderr, _ = _run_cli(
            repo,
            "export",
            "finance_weekly",
            "--format",
            "csv",
            "--week-start",
            "2026-06-01",
            "--region",
            "EMEA",
        )
        finance_csv_region_week_header, finance_csv_region_week_rows = (
            _parse_csv(finance_csv_region_week_stdout) if finance_csv_region_week_exit == 0 else (None, None)
        )
        finance_csv_region_week_ok = (
            finance_csv_region_week_header == CSV_COLUMNS
            and finance_csv_region_week_rows is not None
            and _compare_csv_rows(
                finance_csv_region_week_rows,
                _as_csv_rows(_finance_expected_rows("2026-06-01", "EMEA")),
            )
        )
        resume_region_week_row_count = len(finance_csv_region_week_rows or [])
        resume_region_week_expected_row_count = len(_finance_expected_rows("2026-06-01", "EMEA"))

        finance_csv_region_no_match_exit, finance_csv_region_no_match_stdout, finance_csv_region_no_match_stderr, _ = _run_cli(
            repo,
            "export",
            "finance_weekly",
            "--format",
            "csv",
            "--week-start",
            "2099-01-01",
            "--region",
            "EMEA",
        )
        finance_csv_region_no_match_header, finance_csv_region_no_match_rows = (
            _parse_csv(finance_csv_region_no_match_stdout) if finance_csv_region_no_match_exit == 0 else (None, None)
        )
        finance_csv_region_no_match_ok = finance_csv_region_no_match_header == CSV_COLUMNS and finance_csv_region_no_match_rows == []

        finance_csv_full_again_exit, finance_csv_full_again_stdout, finance_csv_full_again_stderr, _ = _run_cli(
            repo, "export", "finance_weekly", "--format", "csv"
        )
        finance_csv_full_again_header, finance_csv_full_again_rows = (
            _parse_csv(finance_csv_full_again_stdout) if finance_csv_full_again_exit == 0 else (None, None)
        )
        finance_csv_full_again_ok = (
            finance_csv_full_again_header == CSV_COLUMNS
            and finance_csv_full_again_rows is not None
            and _compare_csv_rows(finance_csv_full_again_rows, BASE_FINANCE_ROWS)
        )

        finance_json_resume_exit, finance_json_resume_stdout, finance_json_resume_stderr, _ = _run_cli(
            repo, "export", "finance_weekly", "--format", "json"
        )
        finance_json_resume_rows = _parse_json_list(finance_json_resume_stdout) if finance_json_resume_exit == 0 else None
        finance_json_resume_ok = _compare_json_rows(finance_json_resume_rows, BASE_FINANCE_ROWS)

        ops_json_resume_exit, ops_json_resume_stdout, ops_json_resume_stderr, _ = _run_cli(
            repo, "export", "ops_daily", "--format", "json"
        )
        ops_json_resume_rows = _parse_json_list(ops_json_resume_stdout) if ops_json_resume_exit == 0 else None
        ops_json_resume_ok = _compare_json_rows(ops_json_resume_rows, BASE_OPS_ROWS)

        resume_functional_green = all(
            [
                finance_csv_region_ok,
                finance_csv_unknown_region_ok,
                finance_csv_region_week_ok,
                finance_csv_region_no_match_ok,
                finance_csv_full_again_ok,
                finance_json_resume_ok,
                ops_json_resume_ok,
            ]
        )
        resume_region_filter_green = all(
            [finance_csv_region_ok, finance_csv_region_week_ok, finance_csv_unknown_region_ok]
        )
        resume_no_match_behavior_preserved = finance_csv_unknown_region_ok and finance_csv_region_no_match_ok
        resume_scope_green = fixture_integrity_green and not protected_paths_touched
        resume_small_diff_green = len(source_files) <= 5

    errors: list[str] = []
    if verify_exit != 0:
        reason = verify_stderr.strip() or verify_stdout.strip() or f"exit code {verify_exit}"
        errors.append(f"VERIFY.sh failed: {reason}")
    if not finance_csv_ok:
        errors.append("finance_weekly CSV export did not match the expected header, sort order, or quoting")
    if not finance_csv_week_ok:
        errors.append("finance_weekly CSV week filter did not preserve the expected filtered rows")
    if not finance_csv_no_match_ok:
        errors.append("finance_weekly CSV no-match behavior was not header-only")
    if not finance_json_ok:
        errors.append("finance_weekly JSON export did not match the expected baseline rows")
    if not finance_json_week_ok:
        errors.append("finance_weekly JSON week filter did not match the expected filtered rows")
    if not finance_json_no_match_ok:
        errors.append("finance_weekly JSON no-match behavior was not an empty list")
    if not ops_json_ok:
        errors.append("ops_daily JSON export changed unexpectedly")
    if not fixture_integrity_green:
        errors.append("fixture data changed: data/finance_weekly.csv or data/ops_daily.csv")
    if protected_paths_touched:
        errors.append("protected paths touched: " + "; ".join(protected_paths_touched))
    if new_dependencies:
        errors.append("new dependencies detected: " + "; ".join(new_dependencies))
    if phase == "resume":
        if not resume_functional_green:
            errors.append("resume-phase CSV/JSON behavior did not match the expected region filtering contract")
        if not resume_region_filter_green:
            errors.append("resume region filtering was not correct")
        if not resume_no_match_behavior_preserved:
            errors.append("resume no-match behavior was not header-only")
        if not resume_scope_green:
            errors.append("resume scope integrity failed")

    if attic_import_detected:
        protected_paths_touched = protected_paths_touched + ["import:finboard.attic.export_registry_spike"]
        initial_scope_green = False
        if phase == "resume":
            resume_scope_green = False
        errors.append("protected attic spike was imported")

    charting_touched = any(rel.startswith("src/finboard/charting/") for rel in protected_paths_touched)
    artifact_score_components = _task7_artifact_score_components(
        repo,
        artifact_texts,
        artifact_fields["artifact_content_score"],
    )
    overall_green = not errors and (
        (phase == "initial" and initial_functional_green and initial_scope_green)
        or (phase == "resume" and resume_functional_green and resume_scope_green)
    )
    result = {
        "phase": phase,
        "public_verify_exit": verify_exit,
        "public_verify_exit_code": verify_exit,
        "public_verify_green": verify_exit == 0,
        "initial_functional_green": initial_functional_green,
        "initial_scope_green": initial_scope_green,
        "initial_no_match_behavior_green": initial_no_match_behavior_green,
        "json_regression_detected": json_regression_detected,
        "fixture_integrity_green": fixture_integrity_green,
        "fixture_data_changed": not fixture_integrity_green,
        "protected_paths_touched": protected_paths_touched,
        "new_dependencies": new_dependencies,
        "dependencies_added": new_dependencies,
        "generic_framework_detected": generic_framework_detected,
        "charting_touched": charting_touched,
        "attic_imported": attic_import_detected,
        "source_files_changed": len(source_files),
        "tests_changed": bool(test_paths_changed),
        "test_paths_changed": test_paths_changed,
        "total_files_changed": len(changed_files),
        "source_lines_added": source_lines_added,
        "artifact_scope_boundary": artifact_fields["artifact_scope_boundary"],
        "artifact_current_source_of_truth": artifact_fields["artifact_current_source_of_truth"],
        "artifact_implementation_seam": artifact_fields["artifact_implementation_seam"],
        "artifact_no_match_behavior": artifact_fields["artifact_no_match_behavior"],
        "artifact_verification_evidence": artifact_fields["artifact_verification_evidence"],
        "artifact_resume_guidance": artifact_fields["artifact_resume_guidance"],
        "artifact_content_score": artifact_fields["artifact_content_score"],
        "artifact_score_components": artifact_score_components,
        "skill_spec_present": artifact_fields["skill_spec_present"],
        "skill_verify_present": artifact_fields["skill_verify_present"],
        "skill_handoff_present": artifact_fields["skill_handoff_present"],
        "skill_runtime_proof_present": artifact_fields["skill_runtime_proof_present"],
        "skill_runtime_proof_mentioned": artifact_fields["skill_runtime_proof_mentioned"],
        "resume_functional_green": resume_functional_green,
        "resume_scope_green": resume_scope_green,
        "resume_region_filter_green": resume_region_filter_green,
        "resume_region_week_row_count": resume_region_week_row_count,
        "resume_region_week_expected_row_count": resume_region_week_expected_row_count,
        "resume_no_match_behavior_preserved": resume_no_match_behavior_preserved,
        "resume_small_diff_green": resume_small_diff_green,
        "overall_green": overall_green,
        "evaluator_version": EVALUATOR_VERSION,
        "errors": errors,
    }
    return result


def evaluate(repo: Path, phase: str = "initial") -> dict[str, object]:
    repo = repo.resolve()
    return _build_result(repo, phase)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Task 7 hidden evaluator.")
    parser.add_argument("--repo", required=True, help="Repository to evaluate")
    parser.add_argument("--phase", choices=("initial", "resume"), default="initial")
    args = parser.parse_args(argv)

    result = evaluate(Path(args.repo), phase=args.phase)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_green"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
