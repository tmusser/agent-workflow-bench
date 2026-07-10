# Harness Capabilities

Agent Workflow Bench has separate Claude and Codex execution paths, but both now target the same evidence standard: preserve provider-native sequencing, capture stable workspace states, evaluate those states without steering the agent, and report exactly which claims the resulting trace supports.

This document describes the intended v0.2.0 capability surface. It is a harness rubric, not a model-performance comparison.

## Capability rubric

| Capability | Claude stream-JSON path | Claude polling fallback | Codex JSONL path |
| --- | --- | --- | --- |
| Initial, full-resume, and stripped-resume phases | Yes | Yes | Yes |
| Phase-correct hidden evaluator | Yes | Yes | Yes |
| Public verifier at intermediate checkpoints | Yes | Yes | Yes |
| Hidden evaluator at intermediate checkpoints | Yes | Yes | Yes |
| Functional versus bench-ready green | Yes | Yes | Yes |
| Stable process-group pause during live snapshot | Yes on POSIX | Yes on POSIX | Yes on POSIX |
| Evaluators deferred until agent exit | Yes | Yes | Yes |
| Evaluator output hidden from the agent | Yes | Yes | Yes |
| Native observation unit | Assistant turn plus completed file-changing tool result | Sampled workspace state | Completed provider item |
| First functional-green point | Turn-level when coverage is complete | Not exact | Provider-item level when coverage is complete |
| First bench-ready-green point | Turn-level when coverage is complete | Not exact | Provider-item level when coverage is complete |
| Post-functional activity | Turns and captured states | Sampled states only | Provider items |
| Functional-to-bench-ready gap | Turns/checkpoints | Sampled checkpoints | Provider items |
| Complete-coverage flag | Yes | Always false | Yes |
| Stable-snapshot flag | Yes | Yes | Yes |
| Skipped-state count when capped | Yes | Yes | Yes |
| Snapshot pause overhead recorded | Yes | Yes | Yes |
| Evaluator overhead recorded separately | Yes | Yes | Yes |
| Raw prompts, commands, outputs, and source omitted from normalized trace | Yes | Yes | Yes |

## Shared evidence contract

Both provider paths emit normalized metadata that separates three questions:

1. **When did the workspace first become functionally correct?**
   Public verification and the task-specific hidden evaluator must both pass.
2. **When did the workspace become bench-ready?**
   Functional correctness must pass, plus any arm-specific artifact and proof contract.
3. **How much observable activity followed each point?**
   This distinguishes implementation work, required verification/proof completion, and apparent post-completion activity.

The common coverage fields are:

- `checkpoint_coverage_complete`
- `stable_snapshot_coverage_complete`
- `checkpoint_evaluation_deferred`
- `checkpoint_boundary_resolution`
- `native_observation_unit`
- `workspace_states_observed`
- `workspace_states_skipped`
- `checkpoint_snapshot_pause_seconds`
- `checkpoint_evaluator_seconds`

Claims about the first evaluator-green **observed boundary** require `checkpoint_coverage_complete=true`; neither provider path claims an instruction-level instant.

## Claude semantics

### Stream-JSON mode

Claude emits assistant messages and tool results. The hardened observer captures a distinct workspace state only after a completed file-changing tool result. Assistant boundaries are retained for turn accounting but are not used as snapshot fallbacks because the next turn may already be mutating the workspace when that event is consumed.

Supported claim:

> The first evaluator-green captured Claude turn was turn N.

The observer also records the completed file-changing-tool-result boundary used to capture that state. The turn remains the primary conversational unit because Claude's stream does not expose the same provider-item model as Codex.

A small event-to-pause scheduling race remains. The harness does not claim an instruction-level instant.

### Polling fallback

When stream JSON is unavailable or explicitly disabled, the harness samples workspace state changes. It still pauses the process for stable copies and defers evaluator execution, but sampling can miss intermediate states.

Therefore:

- `checkpoint_coverage_complete=false`
- `solution_latency_observable=false`
- checkpoint indices must not be described as native Claude turns

Polling evidence can describe observed snapshots, but cannot establish the exact first-green point.

## Codex semantics

Codex JSONL exposes ordered provider items. The harness captures distinct states at completed command and file-change item boundaries.

Supported claim when coverage is complete:

> The first evaluator-green captured Codex provider item was item N.

The following fields quantify the native item tail:

- `first_functional_green_item`
- `first_bench_ready_green_item`
- `items_after_first_functional_green`
- `items_after_first_bench_ready_green`
- `functional_to_bench_ready_items`

## What “post-green” does not automatically mean

Do not automatically label all activity after functional green as waste.

For the E arm, work between functional green and bench-ready green may include required:

- verification evidence;
- `VERIFY.md` completion;
- runtime-proof completion;
- handoff or resume artifacts.

Interpret the tails separately:

- **functional-to-bench-ready tail:** potentially required audit work;
- **post-bench-ready tail:** stronger candidate for avoidable continuation;
- **partial-coverage tail:** non-conclusive.

## Provider parity versus provider identity

Parity means the two harnesses apply the same evidence rules and expose the same uncertainty boundaries. It does not mean Claude turns and Codex provider items are interchangeable units.

Cross-provider comparisons should prefer:

- final functional and bench-ready outcomes;
- wall time measured around the agent process only;
- token usage;
- snapshot and evaluator overhead reported separately;
- normalized post-green fractions where the native units differ.

Avoid directly comparing “three Claude turns” with “three Codex items” as if they represented equal work.

## Release boundary

The v0.2.0 observability contract is:

- stable live snapshots where the operating system supports process-group pause;
- evaluator execution deferred until after the agent exits;
- phase-correct hidden evaluators for initial and resume runs;
- explicit complete, partial, and fallback coverage states;
- provider-native first-green and post-green metrics;
- no hidden evaluator feedback injected into the agent session.
