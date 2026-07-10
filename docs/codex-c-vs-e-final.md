# Codex C vs E Final Pilot

Date: 2026-07-10

This artifact records a Codex-only C vs E local pilot for Tasks 1-7. It compares only:

- `C-codex`: Codex no-skill baseline
- `E-ai-engineering-skills`: Codex with the local `ai-engineering-skills` workflow-skill arm

It does not compare these rows against older Claude-backed A/B/E rows. This is single-run local pilot evidence, not broad superiority evidence.

## Model And Settings

```bash
CODEX_MODEL=gpt-5.4-mini
CODEX_PASS_MODEL_FLAG=1
CODEX_PROMPT_MODE=stdin
CODEX_OUTPUT_FORMAT=json
CODEX_EXTRA_ARGS='--json'
CODEX_PERMISSION_MODE=workspace-write
CODEX_PROVIDER=codex
CODEX_RUNNER=codex-cli
CODEX_EFFORT=medium
CODEX_MAX_TURNS=20
SKILL_PLUGIN_DIR="$PWD/local_plugins/ai-engineering-skills"
```

- Codex CLI: `codex-cli 0.144.1`
- Model verification: `codex exec --model gpt-5.4-mini --json --sandbox read-only -` returned `agent_message` `OK`.
- Effort handling: `CODEX_EFFORT=medium` was recorded in provenance and metrics metadata. It was not passed to the Codex CLI; `codex exec --help` exposed `--model` but no reasoning/effort flag.
- Prompt mode: `stdin`
- Output format: Codex JSONL via `--json`
- Permission mode: `workspace-write`
- Max turns label: `20`
- E skill plugin status: local checkout present at `local_plugins/ai-engineering-skills`; E workspaces received `.benchmark/SKILL_RUNTIME_CONTEXT.md`.
- Preflight tests: system Python failed because `pandas` was missing; `.venv/bin/python -m pytest benchmark_harness/tests -q` passed with `232 passed`.

## Task Matrix

| Task | C run ID | C initial status | C full-resume status | C stripped-resume status | E run ID | E initial status | E full-resume status | E stripped-resume status | E proof/artifact status | Concise reading |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 01-support-sla-boundary | `vfinal_codex_01_sla_boundary_C_r1_gpt54mini_medium` | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | `vfinal_codex_01_sla_boundary_E_r1_gpt54mini_medium` | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | proof and `VERIFY.md` were accepted by the validator used during the run; stripped artifacts rebuilt by finalizer | Both arms bench-ready under the original harness; E added audit artifacts without changing the outcome. |
| 02-channel-normalization | `vfinal_codex_02_channel_normalization_C_r1_gpt54mini_medium` | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | `vfinal_codex_02_channel_normalization_E_r1_gpt54mini_medium` | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | proof and `VERIFY.md` were accepted by the validator used during the run; stripped artifacts rebuilt by finalizer | Both arms bench-ready under the original harness; E added audit artifacts. |
| 03-refund-grain | `vfinal_codex_03_refund_grain_C_r1_gpt54mini_medium` | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | `vfinal_codex_03_refund_grain_E_r1_gpt54mini_medium` | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | proof and `VERIFY.md` were accepted by the validator used during the run; stripped artifacts rebuilt by finalizer | Both arms bench-ready under the original harness; E added audit artifacts. |
| 04-impossible-churn | `vfinal_codex_04_impossible_churn_C_r1_gpt54mini_medium` | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | `vfinal_codex_04_impossible_churn_E_r1_gpt54mini_medium` | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | functional green; hidden pass; recovery passed | proof and `VERIFY.md` were accepted by the validator used during the run; stripped artifacts rebuilt by finalizer | Both arms bench-ready under the original harness; E added audit artifacts and tests in some phases. |
| 05-fake-data-analysis | `vfinal_codex_05_fake_data_C_r1_gpt54mini_medium` | public verify pass; hidden fail; recovery `failed: functional` | not run | not run | `vfinal_codex_05_fake_data_E_r1_gpt54mini_medium` | public verify pass; hidden fail; original recovery mislabeled this as `failed: artifact contract`; repaired logic classifies the task outcome as functional failure | not run | not run | E produced `SKILL_RUNTIME_PROOF.md`, `VERIFY.md`, and `HANDOFF.md`; the proof was accepted by the validator used during the run, while the hidden trust gate still failed | Both arms failed the complete hidden trust contract. E was qualitatively closer but still missed denominator inconsistency and leakage. |
| 06-activation-metric-migration | `vfinal_codex_06_activation_C_r1_gpt54mini_medium` | functional green; hidden pass; recovery passed | verify/hidden pass; original recovery false-negative from unrecognized structured output | verify/hidden pass; original recovery false-negative from unrecognized structured output | `vfinal_codex_06_activation_E_r1_gpt54mini_medium` | functional green; hidden pass; recovery passed | verify/hidden pass; original recovery false-negative from unrecognized structured output | verify/hidden pass; original recovery false-negative from unrecognized structured output | E produced `SPEC.md`, `VERIFY.md`, `HANDOFF.md`, and proof accepted by the validator used during the run; functional and artifact status must be assessed separately | Both arms passed the functional and hidden contracts across phases. The original resume failures were parser artifacts, not model failures. |
| 07-dashboard-export-scope-pressure | `vfinal_codex_07_dashboard_export_C_r1_gpt54mini_medium` | hidden evaluator `overall_green=true`; original recovery false-negative from unrecognized JSON | verify/hidden pass; original recovery false-negative from unrecognized structured output | verify/hidden pass; original recovery false-negative from unrecognized structured output | `vfinal_codex_07_dashboard_export_E_r1_gpt54mini_medium` | hidden evaluator `overall_green=true`; original recovery false-negative from unrecognized JSON | verify/hidden pass; original recovery false-negative from unrecognized structured output | verify/hidden pass; original recovery false-negative from unrecognized structured output | E produced `SPEC.md`, `VERIFY.md`, `HANDOFF.md`, and proof accepted by the validator used during the run; the old artifact-contract labels were classification errors | Both arms passed the functional and hidden contracts across phases. E added richer audit evidence without a demonstrated functional or resume advantage. |

## Aggregate Rubric

| Dimension | Result |
| --- | --- |
| Functional correctness | Tasks 1-4 were functional green across C and E. Task 5 failed hidden trust checks in both arms. Tasks 6-7 had public and hidden pass evidence. Their earlier recovery failures were parser artifacts caused by structured evaluator output not being recognized. |
| Hidden evaluator pass/fail | Initial hidden checks passed for Tasks 1-4, 6, and 7 in both arms. Task 5 hidden checks failed in both arms. |
| Full-resume behavior | Tasks 1-4 passed in both arms. Task 5 was not resumed. Tasks 6-7 had verify/hidden pass output; the generic recovery parser previously failed to recognize their structured evaluator status. |
| Stripped-resume behavior | Tasks 1-4 passed in both arms. Task 5 was not resumed. Tasks 6-7 had verify/hidden pass output; the generic recovery parser previously failed to recognize their structured evaluator status. |
| Audit/artifact quality | E produced workflow artifacts on every attempted E initial row. Tasks 1-4 were bench-ready under the validator and classifier versions used during the run. Task 5 shows that artifacts can exist while the hidden contract still fails. Tasks 6-7 show richer E audit evidence without a demonstrated functional or resume advantage. |
| Skill runtime proof validity | Historical E proofs were accepted by the validator version used during the pilot. They have not all been rescored with the newer provider-aware validator, and validator-compatible proof remains agent-declared or artifact-inferred evidence rather than runtime-hook proof. |
| Terminal/turn evidence | Codex JSONL was captured and normalized for all run phases. Metrics reported `actual_turns=1` for each captured phase and `reached_max_turns=false`. |
| Cost/time/token metrics | 38 phase metrics were captured. Aggregate observed totals: `input_tokens=12263079`, `output_tokens=256244`, `reasoning_output_tokens=113602`, `wall_clock_seconds=4737.985`. Cost fields were not populated. |

## Takeaways

### What C Did Well

- C was artifact-producing enough for the harness on Tasks 1-4 and solved the functional bugfix/migration work on Tasks 6-7.
- C preserved the Task 5 hidden failure instead of being rerun to green.
- C gave a useful no-skill baseline for public/hidden behavior under the same Codex CLI runner settings.

### What E Did Well

- E produced audit artifacts (`VERIFY.md`, `SKILL_RUNTIME_PROOF.md`, and, for larger tasks, `SPEC.md` and `HANDOFF.md`) without breaking Tasks 1-4.
- E recovered stripped artifacts on Tasks 1-4 through the finalizer path.
- E made artifact and proof status inspectable in the scorecard and recovery files.

### Where E Added Audit Or Resumability Value

- On Tasks 1-4, E added validator-accepted proof/artifact evidence while matching C's functional green outcome.
- On Tasks 6-7, E left richer audit evidence while matching C's functional result; the original recovery rejection was a parser defect.

### Where Skills Did Not Help Or Added Ceremony

- Task 5 failed hidden analytical trust checks in both arms; E artifacts did not make the answer trustworthy.
- Tasks 6-7 show richer E ceremony without a demonstrated functional or resume advantage.
- E generated more files and larger diffs on several rows, which is useful for audit but not automatically better for small fixes.

### Failures And Limitations

- Task 5 is a real hidden failure for both C and E.
- Task 6 and Task 7 were functional passes; their earlier recovery failures were caused by the generic parser not consuming structured evaluator output.
- The original E artifact-contract labels conflated proof validity with functional status. The repaired classifier reports these as separate axes.
- C arm labels now come from provenance first and fall back to `_C_` run-ID inference.

## Adversarial Reassessment

- The binary functional pattern is tied: both arms passed Tasks 1-4, 6, and 7, and both failed Task 5.
- Task 5 is not a qualitative tie: E rejected the strongest causal overclaim and found the date inconsistency, but still missed denominator inconsistency and leakage.
- In the inspected Task 4-7 initial runs, E used about 2x the wall time and tokens while producing richer audit artifacts.
- Validator-compatible proof is agent-declared evidence, not runtime-hook proof. Provider-specific claims are now checked against the recorded runner for future scoring and validation.

## Rescore Status

- PR #31 repaired the parser, classification, arm attribution, and provider-aware proof validation logic.
- The original local bundles have not yet been rescored with that repaired harness.
- Statements above distinguish direct public/hidden evaluator evidence from the stale recovery labels produced during the original run.
- No model rerun is required to rescore the existing bundles.

## Explicit Limitations

- This is one local pilot.
- It uses one Codex CLI model setting: `CODEX_MODEL=gpt-5.4-mini`.
- It is not a broad benchmark result.
- It is not comparable to old Claude-backed rows.
- It does not establish broad skill superiority or general E-arm superiority.
- Generated bundles are local artifacts and were not committed.

## Reproduction Commands

Preflight:

```bash
git status --short
git log --oneline -5
python -m pytest benchmark_harness/tests -q || .venv/bin/python -m pytest benchmark_harness/tests -q
python -m benchmark_harness.task_catalog --task-slug 01-support-sla-boundary --arm-slug C-codex
python -m benchmark_harness.task_catalog --task-slug 01-support-sla-boundary --arm-slug E-ai-engineering-skills
codex --version
codex exec --help | grep -iE 'reason|effort|model' || true
printf 'Reply OK only.' | codex exec --model gpt-5.4-mini --json --sandbox read-only -
```

Runner settings:

```bash
export PATH="$PWD/.venv/bin:$PATH"
export CODEX_MODEL=gpt-5.4-mini
export CODEX_PASS_MODEL_FLAG=1
export CODEX_PROMPT_MODE=stdin
export CODEX_OUTPUT_FORMAT=json
export CODEX_EXTRA_ARGS='--json'
export CODEX_PERMISSION_MODE=workspace-write
export CODEX_PROVIDER=codex
export CODEX_RUNNER=codex-cli
export CODEX_EFFORT=medium
export CODEX_MAX_TURNS=20
export SKILL_PLUGIN_DIR="$PWD/local_plugins/ai-engineering-skills"
test -d "$SKILL_PLUGIN_DIR"
```

One row pattern:

```bash
TASK_SLUG=01-support-sla-boundary \
ARM_SLUG=C-codex \
RUN_ID=vfinal_codex_01_sla_boundary_C_r1_gpt54mini_medium \
./tools/pilot_codex_smoke.sh auto-c-r1

TASK_SLUG=01-support-sla-boundary \
ARM_SLUG=C-codex \
RUN_ID=vfinal_codex_01_sla_boundary_C_r1_gpt54mini_medium \
./tools/pilot_codex_smoke.sh status
```

Scorecard:

```bash
python -m benchmark_harness.scorecard \
  vfinal_codex_*_gpt54mini_medium-eval-bundle.tar.gz \
  --out benchmark-data/codex-c-vs-e-gpt54mini-medium-scorecard.csv
```
