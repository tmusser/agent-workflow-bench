# Overview

Agent Workflow Bench is a narrow benchmark for an awkward middle of agentic work:
not whether an agent can produce code once, but whether it leaves enough verified
context for the next agent to trust and continue it.

## What It Tests

- Task 4: whether a bugfix remains correct and resumable across fresh-session workflows.
- Task 5: whether an agent resists confident causal overclaiming on suspicious data.
- Task 7: whether an agent keeps a CSV export narrow while extending it through a fresh-session continuation.
- Workflow evidence: whether the run leaves enough artifacts for a later session to resume.
- E-arm behavior: whether the workflow-skill arm can be runtime-proven and artifact-producing.

## What It Does Not Test

- Broad agent superiority across all coding tasks.
- Universal correctness for every programming problem.
- A general leaderboard for all coding agents.
- Any guarantee that workflow skills alone make a bad solution correct.

## How to Read Scorecards

- `green` rows mean the run passed the bundle's functional gates.
- `initial_fail` rows mean the run failed at the initial gate, which is expected for Task 5.
- `artifact_mechanism_active` is only `true` when stripped artifacts were actually removed.
- `skill_runtime_proof_valid` means the proof file passed validation, not just that it existed.

## Current Pilot Lens

- Task 4 is the artifact/resume mechanism test.
- Task 5 is the public-pass / hidden-fail data-trust trap.
- Task 7 is the scope-pressure CSV export and continuation test.
- The current release is intentionally conservative: it reports what the benchmark shows
  without claiming more than the evidence supports.
