from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def replace_once(rel: str, old: str, new: str) -> None:
    text = read(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: expected one exact match, found {count}: {old[:80]!r}")
    write(rel, text.replace(old, new, 1))


def regex_once(rel: str, pattern: str, replacement: str) -> None:
    text = read(rel)
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE | re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{rel}: expected one regex match, found {count}: {pattern[:100]!r}")
    write(rel, new_text)


def append_once(rel: str, marker: str, addition: str) -> None:
    text = read(rel)
    if marker in text:
        return
    if not text.endswith("\n"):
        text += "\n"
    write(rel, text + "\n" + addition.rstrip() + "\n")


EVIDENCE_STATUS = r'''from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

_BOOL_TEXT = {
    "true": True,
    "false": False,
    "1": True,
    "0": False,
    "yes": True,
    "no": False,
    "pass": True,
    "passed": True,
    "fail": False,
    "failed": False,
}

_VERIFY_EXPLICIT_PATTERNS = (
    r"\bverify(?:ication)?(?:_|-|\s)*exit(?:_|-|\s)*(?:code)?\s*[:=]\s*(0|1)\b",
    r"\bverify_exit\s*[:=]\s*(0|1)\b",
    r"\bverification_exit\s*[:=]\s*(0|1)\b",
)
_HIDDEN_EXPLICIT_PATTERNS = (
    r"\bhidden(?:_|-|\s)*evaluator(?:_|-|\s)*exit(?:_|-|\s)*(?:code)?\s*[:=]\s*(0|1)\b",
    r"\bhidden_evaluator_exit\s*[:=]\s*(0|1)\b",
)


def _coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    return _BOOL_TEXT.get(str(value).strip().lower())


def _structured_mapping(text: str) -> dict[str, object]:
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    mapping: dict[str, object] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        key, raw = match.groups()
        boolean = _coerce_bool(raw)
        mapping[key] = boolean if boolean is not None else raw
    return mapping


def _explicit_exit(text: str, kind: str) -> int | None:
    patterns = _VERIFY_EXPLICIT_PATTERNS if kind == "verify" else _HIDDEN_EXPLICIT_PATTERNS
    lowered = text.lower()
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            return int(match.group(1))
    return None


def _structured_exit(text: str, kind: str) -> int | None:
    data = _structured_mapping(text)
    if not data:
        return None

    if kind == "verify":
        for key in ("public_verify_exit_code", "public_verify_exit", "verify_exit", "verification_exit"):
            value = data.get(key)
            if value in (0, 1, "0", "1"):
                return int(value)
        for key in ("public_verify_green", "verification_green", "verify_green"):
            value = _coerce_bool(data.get(key))
            if value is not None:
                return 0 if value else 1
        return None

    overall = _coerce_bool(data.get("overall_green"))
    if overall is not None:
        return 0 if overall else 1

    task6_keys = ("fresh_review_present", "resume_request_complete", "hidden_contract_pass")
    if all(key in data for key in task6_keys):
        values = [_coerce_bool(data.get(key)) for key in task6_keys]
        if all(value is not None for value in values):
            return 0 if all(values) else 1

    hidden_contract = _coerce_bool(data.get("hidden_contract_pass"))
    if hidden_contract is not None:
        errors = data.get("errors")
        if isinstance(errors, list) and errors:
            return 1
        return 0 if hidden_contract else 1

    errors = data.get("errors")
    if isinstance(errors, list):
        return 1 if errors else None
    return None


def infer_exit_from_text(text: str, kind: str) -> int | None:
    if kind not in {"verify", "hidden"}:
        raise ValueError(f"unknown evaluator kind: {kind}")

    explicit = _explicit_exit(text, kind)
    if explicit is not None:
        return explicit

    structured = _structured_exit(text, kind)
    if structured is not None:
        return structured

    lowered = text.lower()
    if kind == "verify":
        fail_markers = (
            "traceback (most recent call last)",
            "assertionerror",
            "failed tests",
            "test session fails",
        )
        fail_regexes = (
            r"^failed\b",
            r"\b[1-9]\d*\s+failed\b",
            r"^error\b",
            r"\b[1-9]\d*\s+errors?\b",
        )
        pass_markers = (
            "passed in",
            "all tests passed",
            "no impossible churn detected",
            "verification passed",
            "verify.sh passed",
        )
    else:
        fail_markers = (
            "traceback (most recent call last)",
            "assertionerror",
            "hidden contract failed",
        )
        fail_regexes = (
            r"^failed\b",
            r"\b[1-9]\d*\s+failed\b",
            r"^error\b",
            r"\b[1-9]\d*\s+errors?\b",
        )
        pass_markers = (
            "hidden task 4 evaluator passed",
            "no hidden contract failed",
            "evaluator passed",
        )

    if any(marker in lowered for marker in fail_markers):
        return 1
    if any(re.search(pattern, lowered, flags=re.MULTILINE) for pattern in fail_regexes):
        return 1
    if any(marker in lowered for marker in pass_markers):
        return 0
    return None


def infer_command_exit(paths: Iterable[Path], kind: str) -> int | None:
    texts: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        explicit = _explicit_exit(text, kind)
        if explicit is not None:
            return explicit
        structured = _structured_exit(text, kind)
        if structured is not None:
            return structured
        texts.append(text)

    for text in texts:
        inferred = infer_exit_from_text(text, kind)
        if inferred is not None:
            return inferred
    return None
'''


def patch_evidence_status() -> None:
    write("benchmark_harness/evidence_status.py", EVIDENCE_STATUS)


def patch_skill_runtime_recovery() -> None:
    rel = "benchmark_harness/skill_runtime_recovery.py"
    replace_once(
        rel,
        "from benchmark_harness.validate_skill_runtime_proof import validate as validate_skill_runtime_proof\n",
        "from benchmark_harness.evidence_status import infer_command_exit\n"
        "from benchmark_harness.validate_skill_runtime_proof import validate as validate_skill_runtime_proof\n",
    )
    regex_once(
        rel,
        r"def _proof_state\(workspace_root: Path\) -> tuple\[bool, bool, list\[str\]\]:.*?return True, not issues, issues\n",
        '''def _proof_state(
    workspace_root: Path,
    *,
    expected_agent_cli: str | None = None,
) -> tuple[bool, bool, list[str]]:
    proof_path = workspace_root / "SKILL_RUNTIME_PROOF.md"
    if not proof_path.exists() or not proof_path.is_file():
        return False, False, ["missing SKILL_RUNTIME_PROOF.md"]
    try:
        issues = validate_skill_runtime_proof(
            proof_path,
            expected_agent_cli=expected_agent_cli,
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        return True, False, [f"{exc.__class__.__name__}: {exc}"]
    return True, not issues, issues
''',
    )
    regex_once(
        rel,
        r"def _infer_exit_code\(path_candidates: list\[Path\], kind: str\) -> int \| str \| None:.*?    return None\n\n",
        '''def _infer_exit_code(path_candidates: list[Path], kind: str) -> int | str | None:
    return infer_command_exit(path_candidates, kind)


''',
    )
    regex_once(
        rel,
        r"def _classify_recovery\(\n    \*,\n    skill_runtime_required: bool,.*?    return \"completed_with_required_artifacts\" if functional_green else \"functional_failure\"\n",
        '''def _classify_recovery(
    *,
    skill_runtime_required: bool,
    proof_required: bool,
    prompt_explicit: bool,
    skill_context_present: bool,
    skill_context_valid: bool,
    proof_present: bool,
    proof_valid: bool,
    functional_green: bool,
    functional_known: bool,
    task_attempted: bool,
    usage_limit_blocked: bool,
    environment_blocked: bool,
    agent_stopped: bool,
    reached_max_turns: bool | str,
) -> str:
    if not task_attempted and usage_limit_blocked:
        return "usage_limit_blocked_before_attempt"
    if not task_attempted and environment_blocked:
        return "environment_blocked_before_attempt"
    if skill_runtime_required and (not skill_context_present or not skill_context_valid):
        return "skill_context_failure"
    if not task_attempted and agent_stopped:
        return "agent_stopped_before_attempt"
    if proof_required and not prompt_explicit:
        return "harness_failure"
    if not functional_known:
        return "harness_failure"
    if not functional_green:
        return "functional_failure"
    if proof_required and not proof_present:
        return "missing_skill_runtime_proof"
    if proof_required and not proof_valid:
        return "artifact_contract_failure"
    return "completed_with_required_artifacts"
''',
    )
    replace_once(
        rel,
        '        f"- Functional green: {\'yes\' if recovery[\'functional_green\'] else \'no\'}",\n',
        '        f"- Functional status: {recovery[\'functional_status\']}",\n'
        '        f"- Artifact status: {recovery[\'artifact_status\']}",\n'
        '        f"- Functional green: {\'yes\' if recovery[\'functional_green\'] else \'no\'}",\n',
    )
    replace_once(
        rel,
        "    run_metrics = _read_json(run_dir / \"run_metrics.json\") or {}\n"
        "    run_provenance = _read_json(run_dir / \"run_provenance.json\") or {}\n",
        "    run_metrics = _read_json(run_dir / \"run_metrics.json\") or {}\n"
        "    run_provenance = _read_json(run_dir / \"run_provenance.json\") or {}\n"
        "    expected_agent_cli = str(run_metrics.get(\"runner\") or run_metrics.get(\"provider\") or \"\").strip() or None\n",
    )
    replace_once(
        rel,
        "    proof_present, proof_valid, proof_issues = _proof_state(workspace_root)\n",
        "    proof_present, proof_valid, proof_issues = _proof_state(\n"
        "        workspace_root,\n"
        "        expected_agent_cli=expected_agent_cli,\n"
        "    )\n",
    )
    replace_once(
        rel,
        "    functional_green = verify_exit == 0 and hidden_exit == 0\n",
        "    functional_known = verify_exit in {0, 1} and hidden_exit in {0, 1}\n"
        "    functional_green = functional_known and verify_exit == 0 and hidden_exit == 0\n"
        "    functional_status = \"passed\" if functional_green else \"failed\" if functional_known else \"unknown\"\n",
    )
    replace_once(
        rel,
        "        functional_green=functional_green,\n"
        "        task_attempted=task_attempted,\n",
        "        functional_green=functional_green,\n"
        "        functional_known=functional_known,\n"
        "        task_attempted=task_attempted,\n",
    )
    replace_once(
        rel,
        "    public_status = _build_public_status(classification, task_attempted=task_attempted)\n",
        "    artifact_status = (\n"
        "        \"not_required\"\n"
        "        if not proof_required\n"
        "        else \"missing\"\n"
        "        if not proof_present\n"
        "        else \"passed\"\n"
        "        if proof_valid\n"
        "        else \"invalid\"\n"
        "    )\n"
        "    public_status = _build_public_status(classification, task_attempted=task_attempted)\n",
    )
    replace_once(rel, '        "schema_version": 1,\n', '        "schema_version": 2,\n')
    replace_once(
        rel,
        '        "functional_green": functional_green,\n',
        '        "functional_known": functional_known,\n'
        '        "functional_green": functional_green,\n'
        '        "functional_status": functional_status,\n'
        '        "artifact_status": artifact_status,\n'
        '        "expected_agent_cli": expected_agent_cli,\n',
    )


def patch_proof_validator() -> None:
    rel = "benchmark_harness/validate_skill_runtime_proof.py"
    replace_once(
        rel,
        "SHA_RE = re.compile(r\"^[0-9a-f]{40}$\")\n\n\n",
        '''SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _agent_family(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    if not normalized:
        return None
    if "codex" in normalized:
        return "codex"
    if "claude" in normalized:
        return "claude"
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or None


''',
    )
    replace_once(
        rel,
        "    allow_runtime_hook: bool = False,\n) -> list[str]:\n",
        "    allow_runtime_hook: bool = False,\n"
        "    expected_agent_cli: str | None = None,\n"
        ") -> list[str]:\n",
    )
    replace_once(
        rel,
        "    elif invocation_evidence_level and invocation_evidence_level not in ALLOWED_INVOCATION_EVIDENCE_LEVELS:\n"
        "        issues.append(\n"
        "            \"Invocation evidence level must be one of: availability_only, artifact_inferred, agent_declared, runtime_hook\"\n"
        "        )\n\n"
        "    return issues\n",
        '''    elif invocation_evidence_level and invocation_evidence_level not in ALLOWED_INVOCATION_EVIDENCE_LEVELS:
        issues.append(
            "Invocation evidence level must be one of: availability_only, artifact_inferred, agent_declared, runtime_hook"
        )

    expected_family = _agent_family(expected_agent_cli)
    actual_agent_cli = _field_value(text, "Agent CLI")
    actual_family = _agent_family(actual_agent_cli)
    if expected_family and actual_family != expected_family:
        issues.append(
            f"Agent CLI {actual_agent_cli or 'missing'} does not match expected runner family {expected_family}"
        )

    environment = (_field_value(text, "Environment variables relevant to skill loading") or "").lower()
    activation = (_field_value(text, "Activation mechanism") or "").lower()
    if expected_family == "codex":
        if "claude_plugin_dir" in environment:
            issues.append("Codex proof must not claim CLAUDE_PLUGIN_DIR as its skill-loading environment")
        if "namespaced skill invocation" in activation:
            issues.append(
                "Codex proof must not claim namespaced skill invocation without provider-native runtime support"
            )

    return issues
''',
    )
    replace_once(
        rel,
        "    parser.add_argument(\n"
        "        \"--allow-template\",\n",
        "    parser.add_argument(\n"
        "        \"--expected-agent-cli\",\n"
        "        help=\"Validate that Agent CLI and loading claims match the actual runner family.\",\n"
        "    )\n"
        "    parser.add_argument(\n"
        "        \"--allow-template\",\n",
    )
    replace_once(
        rel,
        "        allow_runtime_hook=args.allow_runtime_hook,\n"
        "    )\n",
        "        allow_runtime_hook=args.allow_runtime_hook,\n"
        "        expected_agent_cli=args.expected_agent_cli,\n"
        "    )\n",
    )


def patch_e_wrapper() -> None:
    rel = "arms/E-ai-engineering-skills.md"
    replace_once(
        rel,
        "Use the ai-engineering-skills plugin, not just wrapper prose.\n",
        "Use the pinned ai-engineering-skills files when they are actually accessible. Do not claim provider-native skill invocation unless runtime evidence supports it.\n",
    )
    replace_once(
        rel,
        "- Agent CLI: Claude Code\n"
        "- Activation mechanism: namespaced skill invocation from pinned local plugin\n"
        "- Prompt wrapper path: arms/E-ai-engineering-skills.md\n"
        "- Agent-visible skill files: list the actual namespaced skills used\n"
        "- Environment variables relevant to skill loading: CLAUDE_PLUGIN_DIR\n",
        "- Agent CLI: identify the actual active CLI, for example Codex CLI or Claude Code\n"
        "- Activation mechanism: describe only the mechanism supported by evidence; for Codex, use pinned local skill files made available through the runtime context unless stronger evidence exists\n"
        "- Prompt wrapper path: arms/E-ai-engineering-skills.md\n"
        "- Agent-visible skill files: list the actual skill files read or namespaced skills invoked\n"
        "- Environment variables relevant to skill loading: use SKILL_PLUGIN_DIR for Codex or CLAUDE_PLUGIN_DIR for Claude, whichever actually applies\n",
    )


def patch_scorecard() -> None:
    rel = "benchmark_harness/scorecard.py"
    replace_once(
        rel,
        "from benchmark_harness.validate_skill_runtime_proof import validate as validate_skill_runtime_proof\n",
        "from benchmark_harness.evidence_status import infer_command_exit\n"
        "from benchmark_harness.validate_skill_runtime_proof import validate as validate_skill_runtime_proof\n",
    )
    regex_once(
        rel,
        r"def _skill_runtime_proof_valid\(proof_path: Path\) -> bool:.*?        return False\n\n",
        '''def _skill_runtime_proof_valid(
    proof_path: Path,
    *,
    expected_agent_cli: str | None = None,
) -> bool:
    if not proof_path.exists() or not proof_path.is_file():
        return False
    try:
        return not validate_skill_runtime_proof(
            proof_path,
            expected_agent_cli=expected_agent_cli,
        )
    except OSError:
        return False


''',
    )
    replace_once(
        rel,
        "def _arm_slug_from_run_id(run_id: str) -> str:\n"
        "    if \"_A_\" in run_id:\n"
        "        return \"A-baseline\"\n"
        "    if \"_E_\" in run_id:\n"
        "        return \"E-ai-engineering-skills\"\n"
        "    return \"unknown\"\n",
        '''def _arm_slug_from_run_id(run_id: str) -> str:
    if "_A_" in run_id:
        return "A-baseline"
    if "_B_" in run_id:
        return "B-strong-no-skill"
    if "_C_" in run_id:
        return "C-codex"
    if "_E_" in run_id:
        return "E-ai-engineering-skills"
    return "unknown"


def _arm_slug_from_evidence(
    run_id: str,
    metrics: dict[str, object],
    provenance: dict[str, object],
) -> str:
    for key in ("canonical_arm_slug", "resolved_arm_slug", "arm_slug", "requested_arm_slug"):
        value = provenance.get(key) or metrics.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _arm_slug_from_run_id(run_id)
''',
    )
    replace_once(
        rel,
        '        resume_root / "claude_stdout.txt",\n'
        '        resume_root / "claude_stderr.txt",\n',
        '        resume_root / "codex_stdout.txt",\n'
        '        resume_root / "codex_stderr.txt",\n'
        '        resume_root / "claude_stdout.txt",\n'
        '        resume_root / "claude_stderr.txt",\n',
    )
    regex_once(
        rel,
        r"def _infer_command_exit\(candidate_paths: Iterable\[Path\], kind: str\) -> int \| None:.*?    return None\n\n",
        '''def _infer_command_exit(candidate_paths: Iterable[Path], kind: str) -> int | None:
    return infer_command_exit(candidate_paths, kind)


''',
    )
    replace_once(
        rel,
        '        extracted_root / "benchmark-data" / "runs" / run_id / "claude_stdout.txt",\n'
        '        extracted_root / "benchmark-data" / "runs" / run_id / "claude_stderr.txt",\n',
        '        extracted_root / "benchmark-data" / "runs" / run_id / "codex_stdout.txt",\n'
        '        extracted_root / "benchmark-data" / "runs" / run_id / "codex_stderr.txt",\n'
        '        extracted_root / "benchmark-data" / "runs" / run_id / "claude_stdout.txt",\n'
        '        extracted_root / "benchmark-data" / "runs" / run_id / "claude_stderr.txt",\n',
    )
    replace_once(
        rel,
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "claude_stdout.txt",\n'
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "claude_stderr.txt",\n',
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "codex_stdout.txt",\n'
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "codex_stderr.txt",\n'
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "claude_stdout.txt",\n'
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "claude_stderr.txt",\n',
    )
    replace_once(
        rel,
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "claude_stdout.txt",\n'
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "claude_stderr.txt",\n',
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "codex_stdout.txt",\n'
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "codex_stderr.txt",\n'
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "claude_stdout.txt",\n'
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "claude_stderr.txt",\n',
    )
    replace_once(
        rel,
        "        skill_runtime_proof_valid = _skill_runtime_proof_valid(skill_runtime_proof_path)\n",
        "        skill_runtime_proof_valid = _skill_runtime_proof_valid(\n"
        "            skill_runtime_proof_path,\n"
        "            expected_agent_cli=str(initial_metrics.get(\"runner\") or initial_metrics.get(\"provider\") or \"\") or None,\n"
        "        )\n",
    )
    replace_once(
        rel,
        '            "arm_slug": _arm_slug_from_run_id(run_id),\n',
        '            "arm_slug": _arm_slug_from_evidence(run_id, initial_metrics, initial_provenance),\n',
    )


def patch_task5_evaluator() -> None:
    rel = "benchmark_harness/evaluators/task5_hidden_evaluator.py"
    replace_once(
        rel,
        '    re.compile(r"\\bdo not publish\\b", re.I),\n',
        '    re.compile(r"\\bdo not publish\\b", re.I),\n'
        '    re.compile(r"\\bavoid(?: claiming)?\\b", re.I),\n'
        '    re.compile(r"\\breject(?: the)? claim\\b", re.I),\n'
        '    re.compile(r"\\brefrain from\\b", re.I),\n'
        '    re.compile(r"\\bmust not\\b", re.I),\n'
        '    re.compile(r"\\bnever claim\\b", re.I),\n',
    )
    regex_once(
        rel,
        r"def _report_contains_strong_causal_language\(report: dict\[str, object\]\) -> bool:\n    for text in _report_text_values\(report\):\n        if _paragraph_has_unnegated_affirmative_overclaim\(text\):\n            return True\n    return False\n",
        '''def _report_contains_strong_causal_language(report: dict[str, object]) -> bool:
    for field, value in report.items():
        # This field is explicitly a list of claims the report rejects. Treating
        # quoted claims here as affirmative conclusions creates false positives.
        if field == "unsupported_claims":
            continue
        for text in _collect_text_values(value):
            if _paragraph_has_unnegated_affirmative_overclaim(text):
                return True
    return False
''',
    )


def patch_tests() -> None:
    rel = "benchmark_harness/tests/test_skill_runtime_recovery.py"
    replace_once(rel, "- Agent CLI: claude\n", "- Agent CLI: Codex CLI\n")
    replace_once(
        rel,
        "- Activation mechanism: skill directory mounted before run\n",
        "- Activation mechanism: pinned local skill files made available through runtime context\n",
    )
    replace_once(
        rel,
        "- Environment variables relevant to skill loading: CLAUDE_PLUGIN_DIR=/tmp/skills/repo\n",
        "- Environment variables relevant to skill loading: SKILL_PLUGIN_DIR=/tmp/skills/repo\n",
    )
    replace_once(
        rel,
        '                "arm_slug": arm_slug,\n'
        '                "runner_exit_code": codex_exit_code,\n',
        '                "arm_slug": arm_slug,\n'
        '                "provider": "codex",\n'
        '                "runner": "codex-cli",\n'
        '                "runner_exit_code": codex_exit_code,\n',
    )
    append_once(
        rel,
        "test_recovery_parses_task7_structured_green_output",
        r'''
def test_recovery_parses_task7_structured_green_output(tmp_path: Path):
    _, run_dir, workspace = make_run(
        tmp_path,
        "task7-c",
        arm_slug="C-codex",
        prompt_text="# baseline prompt\n",
        context_text=None,
        proof_text=None,
        hidden_text=json.dumps({"overall_green": True, "errors": []}) + "\n",
        task_slug="07-dashboard-export-scope-pressure",
    )

    recovery = skill_runtime_recovery.build_skill_runtime_recovery(
        run_dir=run_dir,
        workspace_root=workspace,
        prompt_file=run_dir / "prompt.md",
        run_id="task7-c",
        task_slug="07-dashboard-export-scope-pressure",
        arm_slug="C-codex",
        phase="initial",
        collect_exit_code=0,
    )

    assert recovery["hidden_evaluator_exit"] == 0
    assert recovery["functional_status"] == "passed"
    assert recovery["classification"] == "completed_with_required_artifacts"


def test_recovery_parses_task6_key_value_green_output(tmp_path: Path):
    _, run_dir, workspace = make_run(
        tmp_path,
        "task6-c",
        arm_slug="C-codex",
        prompt_text="# baseline prompt\n",
        context_text=None,
        proof_text=None,
        hidden_text=(
            "hidden_contract_pass: true\n"
            "fresh_review_present: true\n"
            "resume_request_complete: true\n"
            "errors:\n"
        ),
        task_slug="06-activation-metric-migration",
    )

    recovery = skill_runtime_recovery.build_skill_runtime_recovery(
        run_dir=run_dir,
        workspace_root=workspace,
        prompt_file=run_dir / "prompt.md",
        run_id="task6-c",
        task_slug="06-activation-metric-migration",
        arm_slug="C-codex",
        phase="initial",
        collect_exit_code=0,
    )

    assert recovery["hidden_evaluator_exit"] == 0
    assert recovery["functional_status"] == "passed"
    assert recovery["classification"] == "completed_with_required_artifacts"


def test_e_functional_failure_is_not_mislabeled_as_artifact_failure(tmp_path: Path):
    _, run_dir, workspace = make_run(
        tmp_path,
        "task5-e",
        prompt_text=base_prompt(),
        proof_text=valid_skill_runtime_proof("task5-e"),
        context_text=valid_skill_runtime_context(
            tmp_path / "task5-e" / "benchmark-data" / "runs" / "task5-e"
        ),
        hidden_text="HIDDEN CONTRACT FAILED: missing denominator inconsistency\n",
        task_slug="05-fake-data-analysis",
        collect_exit_code=1,
    )

    recovery = skill_runtime_recovery.build_skill_runtime_recovery(
        run_dir=run_dir,
        workspace_root=workspace,
        prompt_file=run_dir / "prompt.md",
        run_id="task5-e",
        task_slug="05-fake-data-analysis",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        collect_exit_code=1,
    )

    assert recovery["functional_status"] == "failed"
    assert recovery["artifact_status"] == "passed"
    assert recovery["classification"] == "functional_failure"
    assert recovery["failure_category"] == "functional_failure"


def test_unknown_evaluator_output_is_a_harness_failure(tmp_path: Path):
    _, run_dir, workspace = make_run(
        tmp_path,
        "unknown-c",
        arm_slug="C-codex",
        prompt_text="# baseline prompt\n",
        context_text=None,
        proof_text=None,
        hidden_text="structured evaluator emitted no recognized status\n",
    )

    recovery = skill_runtime_recovery.build_skill_runtime_recovery(
        run_dir=run_dir,
        workspace_root=workspace,
        prompt_file=run_dir / "prompt.md",
        run_id="unknown-c",
        task_slug="04-impossible-churn",
        arm_slug="C-codex",
        phase="initial",
        collect_exit_code=1,
    )

    assert recovery["functional_status"] == "unknown"
    assert recovery["classification"] == "harness_failure"
    assert recovery["failure_category"] == "harness_gate_failure"
''',
    )

    rel = "benchmark_harness/tests/test_validate_skill_runtime_proof.py"
    append_once(
        rel,
        "test_expected_codex_runner_rejects_claude_claims",
        r'''
def test_expected_codex_runner_rejects_claude_claims(tmp_path: Path):
    path = tmp_path / "SKILL_RUNTIME_PROOF.md"
    path.write_text(VALID_PROOF, encoding="utf-8")

    issues = validate(path, expected_agent_cli="codex-cli")

    assert any("does not match expected runner family codex" in issue for issue in issues)
    assert any("CLAUDE_PLUGIN_DIR" in issue for issue in issues)


def test_expected_codex_runner_accepts_provider_consistent_proof(tmp_path: Path):
    path = tmp_path / "SKILL_RUNTIME_PROOF.md"
    proof = (
        VALID_PROOF
        .replace("- Agent CLI: claude", "- Agent CLI: Codex CLI")
        .replace(
            "- Activation mechanism: skill directory mounted before run",
            "- Activation mechanism: pinned local skill files made available through runtime context",
        )
        .replace(
            "- Environment variables relevant to skill loading: none",
            "- Environment variables relevant to skill loading: SKILL_PLUGIN_DIR=/tmp/skills/repo",
        )
    )
    path.write_text(proof, encoding="utf-8")

    assert validate(path, expected_agent_cli="codex-cli") == []
''',
    )

    rel = "benchmark_harness/tests/test_task5_hidden_evaluator.py"
    replace_once(
        rel,
        '    report["unsupported_claims"] = ["The campaign caused the lift."]\n',
        '    report["supported_findings"] = ["The campaign caused the lift."]\n',
    )
    append_once(
        rel,
        "test_hidden_evaluator_allows_explicitly_rejected_causal_claim_text",
        r'''
def test_hidden_evaluator_allows_explicitly_rejected_causal_claim_text(tmp_path: Path, monkeypatch):
    _patch_minimal_dataset_hash(monkeypatch)
    repo = _copy_starter(tmp_path)
    _write_minimal_dataset(repo)
    report = _copy_report(MINIMAL_REPORT)
    report["unsupported_claims"] = [
        "The campaign caused the lift.",
        "Avoid claiming that the campaign caused the lift.",
    ]
    _write_outputs(
        repo,
        report,
        (
            "# Executive Summary\n\n"
            "We must not claim that the campaign caused the lift because assignment is undocumented.\n"
        ),
    )

    assert evaluate(repo) == []
''',
    )

    rel = "benchmark_harness/tests/test_scorecard.py"
    append_once(
        rel,
        "test_scorecard_uses_codex_provenance_and_structured_hidden_output",
        r'''
def test_scorecard_uses_codex_provenance_and_structured_hidden_output(tmp_path: Path):
    run_id = "v07pilot_07-dashboard-export_C_r1"
    files = {
        **base_initial_run_files(run_id),
        **base_resume_files(run_id, tag="full"),
        **base_resume_files(run_id, tag="stripped"),
        f"benchmark-data/runs/{run_id}/run_provenance.json": json.dumps(
            {
                "task_slug": "07-dashboard-export-scope-pressure",
                "arm_slug": "C-codex",
                "canonical_arm_slug": "C-codex",
            },
            indent=2,
        )
        + "\n",
        f"benchmark-data/runs/{run_id}/run_metrics.json": json.dumps(
            {
                "task_slug": "07-dashboard-export-scope-pressure",
                "arm_slug": "C-codex",
                "provider": "codex",
                "runner": "codex-cli",
            },
            indent=2,
        )
        + "\n",
        f"benchmark-data/runs/{run_id}/hidden_evaluator_final.txt": json.dumps(
            {"overall_green": True, "errors": []},
            indent=2,
        )
        + "\n",
        f"benchmark-data/resume-runs/{run_id}_full/hidden_evaluator.txt": json.dumps(
            {"overall_green": True, "errors": []},
            indent=2,
        )
        + "\n",
        f"benchmark-data/resume-runs/{run_id}_stripped/hidden_evaluator.txt": json.dumps(
            {"overall_green": True, "errors": []},
            indent=2,
        )
        + "\n",
        f"benchmark-data/resume-runs/{run_id}_full/codex_stdout.txt": "I ran VERIFY.sh and verification passed.\n",
        f"benchmark-data/resume-runs/{run_id}_stripped/codex_stdout.txt": "I ran VERIFY.sh and verification passed.\n",
        f"benchmark-data/workspaces/{run_id}/repo/TASK.md": "# task\n",
        f"benchmark-data/resume-workspaces/{run_id}/stripped/metadata/stripped_artifacts_manifest.json": json.dumps(
            {"removed": [], "kept_required_outputs": [], "skipped": [], "ambiguous_not_removed": [], "dry_run": False},
            indent=2,
        )
        + "\n",
    }
    bundle = make_bundle(tmp_path, run_id, files)

    row = scorecard.score_bundle(bundle)

    assert row["arm_slug"] == "C-codex"
    assert row["initial_hidden_exit"] == 0
    assert row["initial_green"] is True
    assert row["full_resume_hidden_exit"] == 0
    assert row["stripped_resume_hidden_exit"] == 0
    assert row["agent_side_verification_claim"] == "claimed_verified"
''',
    )


def patch_docs() -> None:
    rel = "README.md"
    regex_once(
        rel,
        r"## Codex C vs E Pilot Takeaways\n.*\Z",
        '''## Codex C vs E Pilot Takeaways

[Full Codex C vs E pilot artifact](docs/codex-c-vs-e-final.md)

Benchmarked CLI model: `CODEX_MODEL=gpt-5.4-mini`

Overall reading: in this single Codex-only pilot, C and E had the same observed functional pass pattern. E produced richer audit artifacts and sometimes broader defensive coverage, at materially higher token and wall-time cost. This does not prove native skill invocation caused the differences or that skills broadly outperform no-skill Codex.

| Dimension | What the Codex C vs E pilot shows | What it does not show |
| --- | --- | --- |
| Functional correctness | Both arms passed Tasks 1-4, 6, and 7; both failed Task 5's complete hidden trust contract. | It does not establish a functional win-rate advantage for E. |
| Hidden contracts | Task 5 remained a real failure, although E caught more trust blockers and used more cautious causal language. | A shared binary failure does not mean the two analyses were equally strong. |
| Resume behavior | Tasks 1-4 passed full and stripped resume. Structured Task 6-7 evaluator output was previously misclassified by the generic recovery parser. | It does not show universal resumability or a resume advantage for E. |
| Audit trail quality | E consistently produced richer proof and workflow artifacts. | Artifact presence alone does not establish correctness or native skill invocation. |
| Efficiency | In the inspected Task 4-7 initial rows, E used roughly twice the tokens and wall time. | The sample is too small for a general cost estimate. |
| Overall reading | The evidence supports an auditability-versus-efficiency tradeoff. | It is not proof that skills broadly outperform no-skill Codex. |
''',
    )

    rel = "docs/codex-c-vs-e-final.md"
    text = read(rel)
    text = text.replace(
        "Tasks 6-7 had public/hidden pass evidence, with recovery classifications showing resume/artifact gaps.",
        "Tasks 6-7 had public and hidden pass evidence. Their earlier recovery failures were parser artifacts caused by structured evaluator output not being recognized.",
    )
    text = text.replace(
        "Tasks 6-7 had verify/hidden pass output but failed recovery classification.",
        "Tasks 6-7 had verify/hidden pass output; the generic recovery parser previously failed to recognize their structured evaluator status.",
    )
    text = text.replace(
        "Tasks 6-7 E show that artifacts can exist while hidden or artifact-contract gates still fail.",
        "Task 5 shows that artifacts can exist while the hidden trust gate still fails. Tasks 6-7 are functional passes with richer E audit evidence, not artifact-contract failures.",
    )
    text = text.replace(
        "Tasks 6-7 still failed artifact-contract recovery in resume phases.",
        "The original Task 6-7 artifact-contract labels were classification errors; proof validity and functional status must be reported independently.",
    )
    text = text.replace(
        "On Tasks 6-7, E left richer audit evidence even when the recovery classifier still rejected resume artifact readiness.",
        "On Tasks 6-7, E left richer audit evidence while matching C's functional result; the original recovery rejection was a parser defect.",
    )
    text = text.replace(
        "- Tasks 6-7 show ceremony without bench-ready recovery status in resume phases.\n",
        "- Tasks 6-7 show richer E ceremony without a demonstrated functional or resume advantage.\n",
    )
    text = text.replace(
        "- Task 6 resume phases had verify/hidden pass output but failed recovery classification: C as `functional`, E as `artifact contract`.\n"
        "- Task 7 functional hidden JSON reported `overall_green=true`, but recovery classification still failed: C as `functional`, E as `artifact contract`.\n"
        "- Some scorecard arm labels for C appear as `unknown`; run provenance correctly records `arm_slug` as `C-codex`.\n",
        "- Task 6 and Task 7 were functional passes; their earlier recovery failures were caused by the generic parser not consuming structured evaluator output.\n"
        "- The original E artifact-contract labels conflated valid proof with functional status. The repaired classifier reports these as separate axes.\n"
        "- C arm labels now come from provenance first and fall back to `_C_` run-ID inference.\n",
    )
    text = text.replace(
        "python -m benchmark_harness.scorecard \\\n  vfinal_codex_*_gpt54mini_medium-eval-bundle.tar.gz \\\n  > benchmark-data/codex-c-vs-e-gpt54mini-medium-scorecard.csv",
        "python -m benchmark_harness.scorecard \\\n  vfinal_codex_*_gpt54mini_medium-eval-bundle.tar.gz \\\n  --out benchmark-data/codex-c-vs-e-gpt54mini-medium-scorecard.csv",
    )
    insert = (
        "\n## Adversarial Reassessment\n\n"
        "- The binary functional pattern is tied: both arms passed Tasks 1-4, 6, and 7, and both failed Task 5.\n"
        "- Task 5 is not a qualitative tie: E rejected the strongest causal overclaim and found the date inconsistency, but still missed denominator inconsistency and leakage.\n"
        "- In the inspected Task 4-7 initial runs, E used about 2x the wall time and tokens while producing richer audit artifacts.\n"
        "- Validator-compatible proof is agent-declared evidence, not runtime-hook proof. Provider-specific claims are now checked against the recorded runner.\n"
    )
    if "## Adversarial Reassessment" not in text:
        text = text.replace("\n## Explicit Limitations\n", insert + "\n## Explicit Limitations\n")
    write(rel, text)


def cleanup() -> None:
    for rel in (
        "tools/apply_evidence_fix.py",
        ".github/workflows/apply-evidence-fix.yml",
    ):
        path = ROOT / rel
        if path.exists():
            path.unlink()


def main() -> None:
    patch_evidence_status()
    patch_skill_runtime_recovery()
    patch_proof_validator()
    patch_e_wrapper()
    patch_scorecard()
    patch_task5_evaluator()
    patch_tests()
    patch_docs()
    cleanup()


if __name__ == "__main__":
    main()
