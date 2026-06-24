# Benchmark v0.4.2 Pilot

A small benchmark for agent skills, verification artifacts, and fresh-session resumability.

> A benchmark for the awkward middle of agentic work: not whether an agent can produce code once, but whether it leaves enough verified context for the next agent to trust and continue it.

This is not a universal coding-agent leaderboard.

It is a narrower benchmark for whether workflow skills improve audit trails, verification evidence, and fresh-session resumability on tasks where generic agents may pass public checks while missing hidden contracts.

## 1. What This Is

- A pilot harness for workflow-sensitive agent work.
- A place to test whether an agent can leave durable verification evidence, not just a passing patch.
- A benchmark with two current tasks: one bugfix/resume task and one data-trust task.

## 2. What This Is Not

- Not a universal coding-agent leaderboard.
- Not proof that skill packs broadly outperform baseline.
- Not proof that workflow skills guarantee functional correctness.
- Not proof that these tasks generalize to all coding work.
- Not a public proof benchmark.

## 3. Current Tasks

### Task 4: Impossible Churn Regression

- The visible task fixes a duplicated-join churn bug.
- The benchmark checks whether the fix is durable across resume contexts and whether the agent leaves useful verification evidence.

### Task 5: Fake Data Campaign Lift Trust

- The visible task audits suspicious campaign-lift data without turning it into an overconfident causal story.
- The benchmark checks whether the agent preserves blockers, refuses unsupported claims, and leaves interpretable evidence.

## 4. Arms

### A baseline

- Control arm.
- No workflow skill pack.

### E ai-engineering-skills

- Workflow-skills arm.
- Intended to produce stronger audit trails, verification context, and resumability artifacts.

## 5. Result Interpretation

Proven by the current pilot:

- Task 4: the artifact/resume mechanism works.
- Task 5: the public-pass/hidden-fail data-trust trap works.
- The E arm can be runtime-proven and artifact-producing.

Not proven:

- skill packs broadly outperform baseline.
- skills guarantee functional correctness.
- these tasks generalize to all coding work.

## 6. Quickstart

Run the benchmark tests:

```bash
python -m pytest benchmark_harness/tests -q
```

Run one task through the smoke harness:

```bash
TASK_SLUG=04-impossible-churn \
ARM_SLUG=A-baseline \
RUN_ID=v04pilot_04-bugfix_A_r1 \
./tools/pilot_smoke.sh auto-a-r1
```

For Task 5 details and run examples, see [docs/task5.md](docs/task5.md).

## 7. Scorecard

Summarize bundles:

```bash
python -m benchmark_harness.scorecard <bundles...>
```

The scorecard accepts both `*-eval-bundle.tar.gz` and `*-initial-fail-bundle.tar.gz`.

## 8. Known Limitations

- The pilot is intentionally narrow.
- The current task set is designed to surface workflow and verification behavior, not to rank all agents on all coding work.
- Task 5 yellow rows are useful negative results, not broken scorecard rows.
- Generated artifacts, bundles, and local caches should stay out of source control.

## 9. Roadmap

- Add more tasks that stress different workflow skills.
- Keep public verification and assessment checks separate.
- Continue publishing scorecards and bundles as generated artifacts, not source.
- Improve launch hygiene so the source tree stays easy to inspect and reuse.
