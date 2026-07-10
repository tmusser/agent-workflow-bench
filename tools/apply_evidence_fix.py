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
    if old not in text:
        raise RuntimeError(f"{rel}: missing expected text: {old[:100]!r}")
    write(rel, text.replace(old, new, 1))


def regex_once(rel: str, pattern: str, replacement: str) -> None:
    text = read(rel)
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE | re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{rel}: expected one regex match, found {count}: {pattern[:100]!r}")
    write(rel, new_text)


def patch_scorecard() -> None:
    rel = "benchmark_harness/scorecard.py"
    replace_once(
        rel,
        "from benchmark_harness.solution_latency import summarize_solution_latency\n",
        "from benchmark_harness.evidence_status import infer_command_exit\n"
        "from benchmark_harness.solution_latency import summarize_solution_latency\n",
    )
    regex_once(
        rel,
        r"def _skill_runtime_proof_valid\(proof_path: Path\) -> bool:\n.*?\n\n",
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
    regex_once(
        rel,
        r"def _arm_slug_from_run_id\(run_id: str\) -> str:\n.*?    return \"unknown\"\n",
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
        '        resume_root / "hidden_evaluator.txt",\n        resume_root / "claude_stdout.txt",\n',
        '        resume_root / "hidden_evaluator.txt",\n'
        '        resume_root / "codex_stdout.txt",\n'
        '        resume_root / "codex_stderr.txt",\n'
        '        resume_root / "claude_stdout.txt",\n',
    )
    regex_once(
        rel,
        r"def _infer_command_exit\(candidate_paths: Iterable\[Path\], kind: str\) -> int \| None:\n.*?    return None\n\n",
        '''def _infer_command_exit(candidate_paths: Iterable[Path], kind: str) -> int | None:
    return infer_command_exit(candidate_paths, kind)


''',
    )
    replace_once(
        rel,
        '        extracted_root / "benchmark-data" / "runs" / run_id / "claude_stdout.txt",\n',
        '        extracted_root / "benchmark-data" / "runs" / run_id / "codex_stdout.txt",\n'
        '        extracted_root / "benchmark-data" / "runs" / run_id / "codex_stderr.txt",\n'
        '        extracted_root / "benchmark-data" / "runs" / run_id / "claude_stdout.txt",\n',
    )
    replace_once(
        rel,
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "claude_stdout.txt",\n',
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "codex_stdout.txt",\n'
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "codex_stderr.txt",\n'
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_full" / "claude_stdout.txt",\n',
    )
    replace_once(
        rel,
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "claude_stdout.txt",\n',
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "codex_stdout.txt",\n'
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "codex_stderr.txt",\n'
        '        extracted_root / "benchmark-data" / "resume-runs" / f"{run_id}_stripped" / "claude_stdout.txt",\n',
    )
    replace_once(
        rel,
        '        "claude_stdout.txt",\n        "claude_stderr.txt",\n',
        '        "codex_stdout.txt",\n'
        '        "codex_stderr.txt",\n'
        '        "claude_stdout.txt",\n'
        '        "claude_stderr.txt",\n',
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


def patch_task5() -> None:
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


def add_regression_tests() -> None:
    write(
        "benchmark_harness/tests/test_evidence_status_regressions.py",
        r'''from __future__ import annotations

import json
import textwrap
from pathlib import Path

from benchmark_harness import scorecard, skill_runtime_recovery
from benchmark_harness.evaluators.task5_hidden_evaluator import _paragraph_has_unnegated_affirmative_overclaim
from benchmark_harness.evidence_status import infer_exit_from_text
from benchmark_harness.validate_skill_runtime_proof import validate


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _proof(run_id: str, *, agent_cli: str = "Codex CLI", env: str = "SKILL_PLUGIN_DIR=/tmp/skills") -> str:
    return textwrap.dedent(
        f"""\
        # Skill Runtime Proof

        ## Run
        - Run ID: {run_id}
        - Arm: E-ai-engineering-skills
        - Task: 05-fake-data-analysis
        - Repeat: r1

        ## Skill source
        - Repo URL: https://example.com/repo.git
        - Pinned commit SHA: 0123456789abcdef0123456789abcdef01234567
        - Local path: /tmp/skills
        - Install command: ./benchmark_harness/scripts/pin_skill_repos.sh local_plugins
        - Install stdout/stderr path: benchmark-data/skill-repos/pinned_skill_repos.csv

        ## Activation
        - Agent CLI: {agent_cli}
        - Activation mechanism: pinned local skill files made available through runtime context
        - Prompt wrapper path: arms/E-ai-engineering-skills.md
        - Agent-visible skill files: skills/verify-contract/SKILL.md
        - Environment variables relevant to skill loading: {env}

        ## Pre-run availability check
        - Command run: test -f .benchmark/SKILL_RUNTIME_CONTEXT.md
        - Result: available
        - Evidence path: .benchmark/SKILL_RUNTIME_CONTEXT.md

        ## During-run evidence
        - Invocation evidence level: agent_declared
        - Did the agent mention or invoke the skill? yes
        - Evidence: SKILL_TRACE.jsonl
        - Notes: agent-declared only

        ## Post-run caveat
        - Could a bad result be due to the skill not being loaded? no
        - Reviewer notes: context present
        """
    )


def _context(run_id: str) -> str:
    return textwrap.dedent(
        f"""\
        # Skill Runtime Context
        - Repo URL: https://example.com/repo.git
        - Pinned commit SHA: 0123456789abcdef0123456789abcdef01234567
        - Local plugin path: /tmp/skills
        - Agent-visible plugin path: /tmp/skills
        - Pre-run availability check command: test -f /tmp/skills/PINNED_SKILL_REPO.md
        - Pre-run availability check result: available
        - Pre-run availability evidence path: .benchmark/SKILL_RUNTIME_CONTEXT.md
        - Task slug: 05-fake-data-analysis
        - Arm slug: E-ai-engineering-skills
        - Run ID: {run_id}
        """
    )


def _make_recovery_run(tmp_path: Path, run_id: str, hidden_text: str) -> tuple[Path, Path, Path]:
    run_dir = tmp_path / "runs" / run_id
    workspace = tmp_path / "workspaces" / run_id / "repo"
    prompt = run_dir / "prompt.md"
    _write(prompt, "Create `SKILL_RUNTIME_PROOF.md`.\n")
    _write(run_dir / "verification_final.txt", "3 passed in 0.10s\n")
    _write(run_dir / "hidden_evaluator_final.txt", hidden_text)
    _write(run_dir / "diff.patch", "diff --git a/a.py b/a.py\n")
    _write(run_dir / "diff_stat.txt", "1 file changed\n")
    _write(run_dir / "codex_stdout.txt", '{"type":"turn.completed"}\n')
    _write(run_dir / "codex_stderr.txt", "")
    _write(
        run_dir / "run_metrics.json",
        json.dumps({"runner": "codex-cli", "provider": "codex", "actual_turns": 1, "runner_exit_code": 0}),
    )
    _write(run_dir / "run_provenance.json", json.dumps({"model": "gpt-5.4-mini"}))
    _write(workspace / ".benchmark" / "SKILL_RUNTIME_CONTEXT.md", _context(run_id))
    _write(workspace / "SKILL_RUNTIME_PROOF.md", _proof(run_id))
    return run_dir, workspace, prompt


def test_structured_task7_json_is_green() -> None:
    assert infer_exit_from_text(json.dumps({"overall_green": True, "errors": []}), "hidden") == 0


def test_structured_task6_key_values_are_green() -> None:
    text = "hidden_contract_pass: true\nfresh_review_present: true\nresume_request_complete: true\nerrors:\n"
    assert infer_exit_from_text(text, "hidden") == 0


def test_e_functional_failure_keeps_artifact_status_separate(tmp_path: Path) -> None:
    run_dir, workspace, prompt = _make_recovery_run(
        tmp_path,
        "task5-e",
        "HIDDEN CONTRACT FAILED: missing denominator inconsistency\n",
    )
    result = skill_runtime_recovery.build_skill_runtime_recovery(
        run_dir=run_dir,
        workspace_root=workspace,
        prompt_file=prompt,
        run_id="task5-e",
        task_slug="05-fake-data-analysis",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        collect_exit_code=1,
    )
    assert result["functional_status"] == "failed"
    assert result["artifact_status"] == "passed"
    assert result["classification"] == "functional_failure"


def test_unknown_evaluator_output_is_harness_failure(tmp_path: Path) -> None:
    run_dir, workspace, prompt = _make_recovery_run(tmp_path, "unknown-e", "unrecognized output\n")
    result = skill_runtime_recovery.build_skill_runtime_recovery(
        run_dir=run_dir,
        workspace_root=workspace,
        prompt_file=prompt,
        run_id="unknown-e",
        task_slug="05-fake-data-analysis",
        arm_slug="E-ai-engineering-skills",
        phase="initial",
        collect_exit_code=1,
    )
    assert result["functional_status"] == "unknown"
    assert result["classification"] == "harness_failure"


def test_codex_proof_rejects_claude_specific_claims(tmp_path: Path) -> None:
    path = tmp_path / "SKILL_RUNTIME_PROOF.md"
    path.write_text(_proof("r1", agent_cli="Claude Code", env="CLAUDE_PLUGIN_DIR=/tmp/skills"), encoding="utf-8")
    issues = validate(path, expected_agent_cli="codex-cli")
    assert any("does not match expected runner family codex" in issue for issue in issues)
    assert any("CLAUDE_PLUGIN_DIR" in issue for issue in issues)


def test_scorecard_prefers_provenance_and_recognizes_c_run_ids() -> None:
    assert scorecard._arm_slug_from_evidence(
        "v07pilot_07-dashboard-export_C_r1",
        {"arm_slug": "C-codex"},
        {"canonical_arm_slug": "C-codex"},
    ) == "C-codex"
    assert scorecard._arm_slug_from_run_id("v07pilot_07-dashboard-export_C_r1") == "C-codex"


def test_task5_avoid_claiming_is_negated() -> None:
    assert not _paragraph_has_unnegated_affirmative_overclaim(
        "Avoid claiming that the campaign caused the lift."
    )
''',
    )


def patch_docs() -> None:
    regex_once(
        "README.md",
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
    replacements = {
        "Tasks 6-7 had public/hidden pass evidence, with recovery classifications showing resume/artifact gaps.":
            "Tasks 6-7 had public and hidden pass evidence. Their earlier recovery failures were parser artifacts caused by structured evaluator output not being recognized.",
        "Tasks 6-7 had verify/hidden pass output but failed recovery classification.":
            "Tasks 6-7 had verify/hidden pass output; the generic recovery parser previously failed to recognize their structured evaluator status.",
        "Tasks 6-7 E show that artifacts can exist while hidden or artifact-contract gates still fail.":
            "Task 5 shows that artifacts can exist while the hidden trust gate still fails. Tasks 6-7 are functional passes with richer E audit evidence, not artifact-contract failures.",
        "Tasks 6-7 still failed artifact-contract recovery in resume phases.":
            "The original Task 6-7 artifact-contract labels were classification errors; proof validity and functional status must be reported independently.",
        "On Tasks 6-7, E left richer audit evidence even when the recovery classifier still rejected resume artifact readiness.":
            "On Tasks 6-7, E left richer audit evidence while matching C's functional result; the original recovery rejection was a parser defect.",
        "- Tasks 6-7 show ceremony without bench-ready recovery status in resume phases.\n":
            "- Tasks 6-7 show richer E ceremony without a demonstrated functional or resume advantage.\n",
    }
    for old, new in replacements.items():
        if old in text:
            text = text.replace(old, new)
    old_failures = (
        "- Task 6 resume phases had verify/hidden pass output but failed recovery classification: C as `functional`, E as `artifact contract`.\n"
        "- Task 7 functional hidden JSON reported `overall_green=true`, but recovery classification still failed: C as `functional`, E as `artifact contract`.\n"
        "- Some scorecard arm labels for C appear as `unknown`; run provenance correctly records `arm_slug` as `C-codex`.\n"
    )
    new_failures = (
        "- Task 6 and Task 7 were functional passes; their earlier recovery failures were caused by the generic parser not consuming structured evaluator output.\n"
        "- The original E artifact-contract labels conflated valid proof with functional status. The repaired classifier reports these as separate axes.\n"
        "- C arm labels now come from provenance first and fall back to `_C_` run-ID inference.\n"
    )
    if old_failures in text:
        text = text.replace(old_failures, new_failures)
    text = text.replace(
        "python -m benchmark_harness.scorecard \\\n  vfinal_codex_*_gpt54mini_medium-eval-bundle.tar.gz \\\n  > benchmark-data/codex-c-vs-e-gpt54mini-medium-scorecard.csv",
        "python -m benchmark_harness.scorecard \\\n  vfinal_codex_*_gpt54mini_medium-eval-bundle.tar.gz \\\n  --out benchmark-data/codex-c-vs-e-gpt54mini-medium-scorecard.csv",
    )
    if "## Adversarial Reassessment" not in text:
        reassessment = (
            "\n## Adversarial Reassessment\n\n"
            "- The binary functional pattern is tied: both arms passed Tasks 1-4, 6, and 7, and both failed Task 5.\n"
            "- Task 5 is not a qualitative tie: E rejected the strongest causal overclaim and found the date inconsistency, but still missed denominator inconsistency and leakage.\n"
            "- In the inspected Task 4-7 initial runs, E used about 2x the wall time and tokens while producing richer audit artifacts.\n"
            "- Validator-compatible proof is agent-declared evidence, not runtime-hook proof. Provider-specific claims are now checked against the recorded runner.\n"
        )
        text = text.replace("\n## Explicit Limitations\n", reassessment + "\n## Explicit Limitations\n")
    write(rel, text)


def cleanup() -> None:
    for rel in ("tools/apply_evidence_fix.py", ".github/workflows/apply-evidence-fix.yml"):
        path = ROOT / rel
        if path.exists():
            path.unlink()


def main() -> None:
    patch_scorecard()
    patch_task5()
    add_regression_tests()
    patch_docs()
    cleanup()


if __name__ == "__main__":
    main()
