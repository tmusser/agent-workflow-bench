# Agent Workflow Bench

[![CI](https://github.com/tmusser/agent-workflow-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/tmusser/agent-workflow-bench/actions/workflows/ci.yml)
[![Python >=3.11](https://img.shields.io/badge/python-%3E%3D3.11-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Version v0.1.0](https://img.shields.io/badge/version-v0.1.0-informational)](https://github.com/tmusser/agent-workflow-bench/releases/tag/v0.1.0)

A small benchmark for agent skills, verification artifacts, and fresh-session resumability.

> A benchmark for the awkward middle of agentic work: not whether an agent can produce code once, but whether it leaves enough verified context for the next agent to trust and continue it.

This is not a universal coding-agent leaderboard.

It is a narrower benchmark for whether workflow skills improve audit trails, verification evidence, and fresh-session resumability on tasks where generic agents may pass public checks while missing hidden contracts.

For a compact summary, see [docs/overview.md](docs/overview.md).
For deterministic artifact hygiene checks, see [docs/artifact-usability.md](docs/artifact-usability.md).
For inferred skill evidence summaries, see [docs/skill-routing-summary.md](docs/skill-routing-summary.md).
For agent-declared trace evidence, see [docs/skill-trace.md](docs/skill-trace.md).

## 1. What This Is

- A pilot harness for workflow-sensitive agent work.
- A place to test whether an agent can leave durable verification evidence, not just a passing patch.
- A benchmark with current tasks covering localized bugfixes, normalization bugs, aggregation-grain bugs,
  bugfix/resume behavior, data-trust traps, activation-metric migration, and scope-pressure exports.

## 2. What This Is Not

- Not a universal coding-agent leaderboard.
- Not proof that skill packs broadly outperform baseline.
- Not proof that workflow skills guarantee functional correctness.
- Not proof that these tasks generalize to all coding work.
- Not a proof of broad agent superiority.

## 3. Current Tasks

### Task 1: Support SLA Boundary Regression

- The visible task fixes an inclusive/exclusive SLA deadline bug.
- The benchmark checks whether the fix is localized, preserves the report shape, and avoids fixture edits or hardcoded fixture answers.
- The current Haiku pilot is a low-ceremony smoke: A and E both pass, and the lighter E wrapper is viable and artifact-producing but not clearly more efficient in aggregate.
- See [docs/task1.md](docs/task1.md).

### Task 2: Campaign Channel Normalization

- The visible task fixes messy acquisition-channel labels that split equivalent rows.
- The benchmark checks whether the agent normalizes inputs without changing fixtures, report shape, or expected grouping behavior.
- The current Haiku pilot is a bridge smoke: A and E both pass; E has better aggregate run metrics in this single sample, but this is suggestive rather than proof of broad superiority.
- See [docs/task2.md](docs/task2.md).

### Task 3: Product Refund Grain Regression

- The visible task fixes a refund-rate report that counts refund events instead of refunded orders.
- The benchmark checks whether the agent preserves the report path while correcting the aggregation grain.
- The current Haiku pilot is a bridge smoke: A and E both pass; E leaves stronger audit/proof evidence in initial/full contexts and is cheaper/faster overall in this single sample, while A had cleaner terminal completions in initial/full. Treat this as audit evidence, not broad superiority evidence.
- See [docs/task3.md](docs/task3.md).

### Task 4: Impossible Churn Regression

- The visible task fixes a duplicated-join churn bug.
- The benchmark checks whether the fix is durable across resume contexts and whether the agent leaves useful verification evidence.
- The observer-aware Haiku rerun validates the solution-latency checkpoint path and artifact gate. A baseline passed public + hidden checks across initial, full-resume, and stripped-resume phases with observable `stream_json` first-green telemetry. The E arm became functionally green in the initial phase but failed the bench-ready artifact gate because `SKILL_RUNTIME_PROOF.md` was missing, so E full/stripped resume phases were not run. Treat this as artifact-gate evidence, not an E-arm success or broad superiority claim.
- Efficiency claims require observable first-green telemetry. Runs without per-turn or checkpoint evidence remain final-only and must not be used to infer first-green latency.

### Task 5: Fake Data Campaign Lift Trust

- The visible task audits suspicious campaign-lift data without turning it into an overconfident causal story.
- The benchmark checks whether the agent preserves blockers, refuses unsupported claims, and leaves interpretable evidence.

### Task 6: Activation Metric v2 Migration

- Planned / under construction. See [docs/task6.md](docs/task6.md).

### Task 7: Finance Weekly CSV Export

- A scoped dashboard export task under pressure to widen the implementation.
- The benchmark checks whether the agent preserves existing JSON behavior, keeps CSV support narrow, and handles fresh-session continuation.
- See [docs/task7.md](docs/task7.md).

## 4. Arms

### A baseline

- Control arm.
- No workflow skill pack.

### E ai-engineering-skills

- Workflow-skills arm.
- Intended to produce stronger audit trails, verification context, and resumability artifacts.
- E-arm setup and validation: [docs/skill-arm-setup.md](docs/skill-arm-setup.md)

## 5. Result Interpretation

Proven by the current pilot:

- Task 1: the low-ceremony smoke works; both A and E solve the simple boundary bug across initial/full/stripped phases.
- Task 1: E-arm viability depends on ceremony calibration. The lighter E wrapper is artifact-producing and resume-ready; the earlier heavier generic wrapper was not viable under the same 20-turn budget.
- Task 2: the input-normalization bridge smoke works; both A and E solve the channel-normalization bug across initial/full/stripped phases.
- Task 2: in one Haiku sample, E had slightly better aggregate run metrics and produced validator-compatible proof artifacts, but the task is still too small for broad performance claims.
- Task 3: the refund-grain bridge smoke works; both A and E solve the entity-count versus event-count bug across initial/full/stripped phases.
- Task 3: in one Haiku sample, E was cheaper/faster overall and had fewer Bash denials, while A had cleaner terminal completions in initial/full contexts. This is audit evidence, not an E-arm superiority claim.
- Task 4: the observer-aware bridge smoke validates the checkpoint path and artifact gate. A baseline passed initial/full/stripped with observable first-green telemetry; E became functionally green in initial but failed bench-ready artifact compliance because `SKILL_RUNTIME_PROOF.md` was missing, so E resume phases were not run.
- Task 5: the public-pass/hidden-fail data-trust trap works.
- Task 7: sharper invalidation around compatibility seams and test integrity is more useful than heavier ceremony.
- The E arm can be runtime-proven and artifact-producing.

Not proven:

- skill packs broadly outperform baseline.
- skills guarantee functional correctness.
- these tasks generalize to all coding work.
- Tasks 1-3 prove a broad performance advantage for skills. They are low-ceremony smoke / bridge tasks.

### Current task evidence summary

This table reflects the current pilot, not a universal result set.

| Task | Status | Evidence / reading |
| --- | --- | --- |
| Task 1 | piloted smoke | A and lighter E both pass public + hidden checks across initial, full-resume, and stripped-resume phases. E is viable and artifact-producing, but not clearly more efficient in aggregate. |
| Task 2 | piloted bridge smoke | A and E both pass public + hidden checks across initial, full-resume, and stripped-resume phases. E is artifact-producing and slightly better on aggregate run metrics in this sample; treat as suggestive only. |
| Task 3 | piloted bridge smoke | A and E both pass public + hidden checks across initial, full-resume, and stripped-resume phases. E is artifact-producing and cheaper/faster overall in this sample, while A has cleaner terminal completions in the initial and full-resume phases. |
| Task 4 | observer-piloted / mixed | A baseline passed initial/full/stripped with observable first-green telemetry. E became functionally green in initial but failed bench-ready artifact compliance because `SKILL_RUNTIME_PROOF.md` was missing; E resume phases were not run. This validates the observer and artifact gate, not broad skill superiority. |
| Task 5 | piloted negative control | Public checks could pass while hidden denominator/leakage traps still failed; clearer audit trails helped inspection but did not guarantee correctness. |
| Task 6 | under construction | Activation metric migration harness exists but should not be advertised as a completed pilot result yet. |
| Task 7 | piloted / hardened | Stronger settings saturated on behavior; weaker settings exposed API seam and test-integrity failures. The hardening lesson was sharper invalidation, not more process. |

### Illustrative current-pilot scorecard rows

These rows are examples of the current scorecard shape. They are not a complete leaderboard.

| Task | Arm | Scorecard shape | Artifact mechanism | Reading |
| --- | --- | --- | --- | --- |
| Task 1 | A baseline | green | inactive | Functional pass across initial/full/stripped on a one-line SLA boundary fix. |
| Task 1 | E ai-engineering-skills | green / skill proof + artifacts | active | Functional pass with `VERIFY.md` and validator-compatible `SKILL_RUNTIME_PROOF.md`; useful smoke for ceremony calibration, not broad superiority evidence. |
| Task 2 | A baseline | green | inactive | Functional pass across initial/full/stripped on an input-normalization bridge task; some extra generated local files appeared in the workspace. |
| Task 2 | E ai-engineering-skills | green / skill proof + artifacts | active | Functional pass with `VERIFY.md` and validator-compatible `SKILL_RUNTIME_PROOF.md`; slightly better aggregate run metrics in this single sample. |
| Task 3 | A baseline | green | inactive | Functional pass across initial/full/stripped on a refund-grain bridge task; initial and full-resume completed cleanly, but stripped hit `max_turns`. |
| Task 3 | E ai-engineering-skills | green / skill proof + artifacts | active | Functional pass with `VERIFY.md` and validator-compatible `SKILL_RUNTIME_PROOF.md`; cheaper/faster overall in this sample, with fewer Bash denials but noisier terminal reasons. |
| Task 4 | A baseline | green | inactive | Functional pass across initial/full/stripped on the impossible-churn bugfix with observable first-green telemetry. |
| Task 4 | E ai-engineering-skills | initial green / bench-ready fail | inactive | Functionally green in initial, but bench-ready artifact compliance failed because `SKILL_RUNTIME_PROOF.md` was missing; E resume phases were not run. |
| Task 5 | A baseline | initial_fail / hidden fail | inactive | Expected negative result from the public-pass / hidden-fail trap. |
| Task 5 | E ai-engineering-skills | initial_fail / skill proof + artifacts / hidden fail | inactive | Skill proof and workflow artifacts are present, but the hidden trust gate still fails. |
| Task 7 | B / E stronger settings | behavior saturated | varies | Strong prompting and skill routing both reached the narrow behavior in stronger settings. |
| Task 7 | weaker settings | hidden failures exposed | varies | Compatibility seams, no-match behavior, and test-integrity checks caught fragile implementations. |

## 6. Quickstart

Run the benchmark tests:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest benchmark_harness/tests -q
```

Run one task through the smoke harness:

```bash
TASK_SLUG=01-support-sla-boundary \
ARM_SLUG=A-baseline \
RUN_ID=v01pilot_01-sla-boundary_A_r1 \
./tools/pilot_smoke.sh auto-a-r1
```

Run the same harness under deterministic context pressure:

```bash
TASK_SLUG=04-impossible-churn \
ARM_SLUG=A-baseline \
RUN_ID=v04pilot_04-bugfix_A_pressure_r1 \
./tools/pilot_smoke.sh --pressure-level medium --pressure-seed 7 --context-window-tokens 32000 init
```

The built-in pressure levels target a stable fraction of the configured context window:
`none=0%`, `low=5%`, `medium=15%`, `high=35%`. An optional `--pressure-target-pct`
override is available for manual experiments.

Summarize deterministic artifact hygiene for a run:

```bash
python -m benchmark_harness.artifact_usability summarize-run --run-id "$RUN_ID" --phase initial
```

Summarize inferred skill evidence for a run:

```bash
python -m benchmark_harness.skill_routing_summary summarize-run --run-id "$RUN_ID" --phase initial
```

For Task 1 details and run examples, see [docs/task1.md](docs/task1.md).
For Task 2 details and run examples, see [docs/task2.md](docs/task2.md).
For Task 3 details and run examples, see [docs/task3.md](docs/task3.md).
For Task 5 details and run examples, see [docs/task5.md](docs/task5.md).
For Task 7 details and run examples, see [docs/task7.md](docs/task7.md).
For the pressure-slice workflow and summary table, see [docs/pressure-slice.md](docs/pressure-slice.md).

## 7. Scorecard

Summarize bundles:

```bash
python -m benchmark_harness.scorecard <bundles...>
```

The scorecard accepts both `*-eval-bundle.tar.gz` and `*-initial-fail-bundle.tar.gz`.

## 8. Known Limitations

- The pilot is intentionally narrow.
- The current task set is designed to surface workflow and verification behavior, not to rank all agents on all coding work.
- Tasks 1-3 are low-ceremony smoke / bridge tasks and should not be read as evidence of broad skill superiority.
- Task 5 yellow rows are useful negative results, not broken scorecard rows.
- Generated artifacts, bundles, and local caches should stay out of source control.
- The benchmark now separates skill availability, artifact-inferred evidence, and agent-declared trace evidence. True runtime-hook invocation tracing remains future work.
- The scorecard still reports the older artifact-focused rows. Future columns may expose `skill_available`, `artifact_inferred`, `agent_declared_trace`, and `runtime_hook_trace`.
- Runs without per-turn or checkpoint evidence remain final-only, so `terminal_reason=max_turns` does not imply the solution first became correct at the final turn. Efficiency claims require observable first-green telemetry.
- Context pressure measures degradation under constrained, cluttered context. It does not by itself establish broad model superiority; compare like-for-like tasks, arms, and pressure settings.

## 9. Roadmap

- Add more tasks that stress different workflow skills.
- Keep public verification and assessment checks separate.
- Continue publishing scorecards and bundles as generated artifacts, not source.
- Improve launch hygiene so the source tree stays easy to inspect and reuse.
- PyPI publishing is deferred until the repo exposes a stable CLI and package-data story.
