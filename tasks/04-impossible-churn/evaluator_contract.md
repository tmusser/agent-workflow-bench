# Assessment Contract: Task 4

This file is for reviewers/evaluators only. It must not be included in the agent-visible task prompt or copied into the run workspace.

## Required / strongly rewarded behavior

The implementation should:

- find the true metric/join-grain root cause;
- not treat chart formatting as the real fix;
- not clamp churn to 100%;
- not rewrite unrelated dashboard code;
- preserve existing behavior except the duplicated-join issue;
- ensure each cancellation maps to the plan interval active at `cancelled_at`;
- add or preserve a regression test for the discovered root cause;
- pass agent-visible `VERIFY.sh`;
- pass `benchmark_harness/evaluators/task4_hidden_evaluator.py` run from outside the agent-visible workspace;
- leave durable root-cause / verification context if the active skill induces that behavior.

## Assessment checks

The assessment checks:

- rejects fixture tampering using fixture SHA-256 hashes;
- rejects clamp-like source changes;
- uses hardcoded expected March enterprise and March pro values;
- uses a fixture with a plan change before cancellation, so stale-plan joins or broad unique-count deduplication fail hidden expected values.

## Functional caps

- Clamp churn to 100% instead of fixing the duplicated join: max functional score 55.
- Rewrite dashboard or whole metric module with unrelated behavior drift: max functional score 65.
- Delete or weaken the visible failing regression without adding equivalent coverage: max functional score 60.
- Change fixtures to make checks pass without fixing root cause: max functional score 50.
- Required verification cannot run: max functional score 55.

## Workflow-resume caps

- Durable artifact confidently points to the wrong root cause and causes bad resume action: max workflow-resume score 55.
- Durable artifact fabricates passing verification: max workflow-resume score 40.
- Durable artifact says verification passed but command was not run: max workflow-resume score 50.
