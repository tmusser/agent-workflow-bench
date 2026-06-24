# v0.4.2 Pilot Scoring Guide

## Headline scores

Report these internally for the pilot:

```text
Functional score
Workflow-resume score
artifact_resume_delta
```

Do not publish a public benchmark report from v0.4.2 pilot alone.

## Functional score, 100 points

| Category | Weight |
|---|---:|
| Correct root-cause fix | 30 |
| Required verification passes | 20 |
| Regression coverage | 15 |
| Maintainability | 12 |
| Minimality / overbuild avoidance | 12 |
| Existing behavior preserved | 6 |
| Runtime/tool reliability | 5 |

## Workflow-resume score, 100 points

| Category | Weight |
|---|---:|
| Fresh-session reconstruction accuracy | 20 |
| Verification evidence quality | 18 |
| Scope/control evidence | 15 |
| Durable artifact usefulness | 15 |
| Rediscovery burden | 12 |
| Assumption/risk capture | 8 |
| Handoff/next-step clarity | 7 |
| Artifact efficiency | 5 |

## Artifact resume delta

```text
artifact_resume_delta =
  workflow_resume_score_full_workspace
  - workflow_resume_score_artifact_stripped_workspace
```

This measures leftover workflow artifact value for fresh-session resumption after implementation is complete. It does not isolate the full causal value of workflow gates during the initial implementation path.

## Misleading-artifact caps

- Durable artifact confidently points to the wrong root cause and causes bad resume action: workflow-resume score max 55.
- Durable artifact fabricates passing verification: workflow-resume score max 40.
- Durable artifact says verification passed but command was not run: workflow-resume score max 50.
- Internally contradictory artifacts force rediscovery from code/tests: artifact usefulness max 2/5.

## Artifact bloat review

Workflow artifact line budget for Task 4: 120 Markdown lines.

If workflow-artifact lines exceed the budget, reviewers must answer:

1. Did the extra content materially reduce verification or resume effort?
2. Did the fresh session rely on the extra content?
3. Did the extra content prevent a plausible mistake?
4. Was any content stale, duplicated, vague, or misleading?
5. Would a shorter artifact have worked as well?

Only apply a bloat penalty if extra artifact volume did not help the fresh session or reviewer.
