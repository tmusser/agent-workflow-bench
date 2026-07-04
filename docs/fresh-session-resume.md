# Fresh-Session Resume Evaluation

Fresh-session resume evaluation turns durable artifacts into a measurable condition
instead of a vibe.

The core question is:

> Given the same completed initial workspace, does a fresh continuation run perform
> better when workflow artifacts are present than when they are stripped?

This is deliberately narrower than a general artifact-quality judge. The harness
measures whether artifacts help a new agent continue the work under controlled
conditions.

## Conditions

The first standardized comparison uses the existing resume workspace layout:

| Condition | Workspace | Meaning |
| --- | --- | --- |
| `full` | `benchmark-data/resume-workspaces/<RUN_ID>/full/repo` | Continuation workspace with durable artifacts preserved. |
| `stripped` | `benchmark-data/resume-workspaces/<RUN_ID>/stripped/repo` | Same continuation workspace after workflow artifacts are stripped by the task manifest. |

The condition metadata stays outside the agent-visible repository. The fresh agent
should see only the repository state and the continuation prompt, not the condition
label.

## Run Flow

A typical manual flow is still:

```bash
TASK_SLUG=07-dashboard-export-scope-pressure \
ARM_SLUG=E-ai-engineering-skills \
RUN_ID=v07pilot_07-dashboard-export_E_r1 \
./tools/pilot_smoke.sh init

# Run the initial agent, then:
./tools/pilot_smoke.sh collect-initial

# Run the fresh agent in the full workspace, then:
./tools/pilot_smoke.sh collect-full

# Run the fresh agent in the stripped workspace, then:
./tools/pilot_smoke.sh collect-stripped
```

After the fresh agents have run, use `evaluate` to run local verification and hidden
evaluator checks for both fresh-session workspaces and write the summary JSON:

```bash
python -m benchmark_harness.fresh_session_resume evaluate \
  --run-id "$RUN_ID" \
  --resume-evaluator-module benchmark_harness.evaluators.task7_resume_evaluator
```

This writes:

```text
benchmark-data/runs/<RUN_ID>/fresh_session_resume_summary.json
```

`evaluate` does not invoke an LLM. It runs `./VERIFY.sh`, runs the selected hidden
evaluator, captures diff/status outputs, copies known review artifacts, writes
`verification_exit_code.txt` and `hidden_evaluator_exit_code.txt` sidecars, and writes
the summary JSON.

If those exit-code sidecars already exist, you can summarize existing outputs without
rerunning local checks:

```bash
python -m benchmark_harness.fresh_session_resume summarize \
  --run-id "$RUN_ID"
```

`summarize` is intentionally read-only. It does not infer pass/fail from verifier text.
If the sidecar exit-code files are missing, the comparison is marked `incomplete`.

## Summary Shape

The summary is intentionally boring JSON:

```json
{
  "schema_version": 1,
  "run_id": "v07pilot_07-dashboard-export_E_r1",
  "conditions": [
    {
      "condition": "full",
      "workspace_exists": true,
      "attempted": true,
      "verify_exit_code": 0,
      "hidden_evaluator_exit_code": 0,
      "passed": true,
      "workflow_artifacts_present": ["HANDOFF.md", "VERIFY.md"]
    }
  ],
  "comparison": {
    "full_vs_stripped": {
      "status": "complete",
      "winner": "full",
      "artifact_advantage_observed": true
    }
  }
}
```

The comparison is intentionally conservative:

- `full` wins only when full passes and stripped does not.
- `stripped` wins only when stripped passes and full does not.
- both pass or both fail is a `tie`.
- missing exit-code files make the comparison `incomplete`.

## Interpretation

A full-condition win is evidence that durable artifacts helped continuation on that
run. It is not proof that the skill pack always helps.

A tie is still useful:

- both pass: the task may not need artifacts, or the fresh prompt is strong enough;
- both fail: the task may be too hard, the continuation prompt may be underspecified,
  or both workspaces may lack the right state.

The value is not just the winner. The machine-readable summary makes resume behavior
repeatable, comparable, and bundleable across tasks and arms.
