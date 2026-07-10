# Solution latency

Solution latency records when a run first becomes functionally green and when it first becomes bench-ready green. It is intended to separate useful work from post-solution churn without pretending that every provider exposes equivalent turn-level telemetry.

## Core fields

- `first_functional_green_turn`: first observed turn whose public verifier and hidden evaluator both pass.
- `first_bench_ready_green_turn`: first observed turn that also satisfies the arm-specific artifact contract.
- `turns_after_first_functional_green`: observed turns after functional success.
- `turns_after_first_bench_ready_green`: observed turns after bench-ready success.
- `functional_to_bench_ready_turns`: the gap between functional and bench-ready success when available.
- `solution_latency_observable`: whether the evidence supports first-green timing claims.
- `solution_latency_source`: the observation mechanism.
- `solution_latency_note`: the applicable claim boundary.

These fields should be interpreted together. A final green workspace does not imply that the first-green turn was observed.

## Observation modes

### Claude stream JSON

When Claude emits usable stream JSON, the observer records assistant boundaries and tool metadata. After a turn that changed files completes, it snapshots the repository and runs the public and hidden evaluators against the snapshot.

This supports turn-level first-green observation when checkpoints were successfully captured.

### Claude modification-time polling

When stream JSON is unavailable, the observer polls relevant tracked files. A changed signature creates a checkpoint and evaluator snapshot.

This is checkpoint-level rather than conversational-turn evidence. The synthetic checkpoint index must not be presented as a native provider turn.

### Final-only provider output

When no intermediate events or checkpoints are available, only the final result is observable. Keep first-green fields empty and use:

- `solution_latency_observable=false`
- `solution_latency_source=final_only_no_per_turn_trace`

Do not infer first-green timing from the final pass.

## Checkpoint behavior

Each checkpoint:

1. copies the current workspace to an isolated temporary directory;
2. runs `VERIFY.sh` against the copy;
3. runs the task-specific hidden evaluator against the copy;
4. evaluates the arm-specific bench-ready contract;
5. writes safe metadata and evaluator output beneath `solution_latency_checkpoints/`;
6. removes the temporary copy.

The evaluator runs against the copy so it cannot mutate the agent's live workspace.

Checkpoint errors are evidence gaps. They are written to `checkpoint_eval_errors` and must not be silently converted into task failures.

## Functional versus bench-ready green

Functional green means:

```text
VERIFY.sh exit == 0
AND hidden evaluator exit == 0
```

Bench-ready green additionally applies the arm-specific contract.

For the current arms:

- `A-baseline`: bench-ready equals functional green.
- `B-*` and `C-*`: bench-ready equals functional green unless a task-specific contract says otherwise.
- `E-ai-engineering-skills`: bench-ready requires functional green plus `VERIFY.md` and a valid `SKILL_RUNTIME_PROOF.md`.

## Codex item timeline

Codex `exec --json` can expose one provider turn while still emitting many ordered
`item.started`, `item.completed`, and `item.updated` records. The normalized trace now
keeps those as a separate provider-item timeline instead of pretending each command is
a conversational turn.

The item timeline records safe metadata only and omits raw commands, outputs, and paths.
It can report:

- distinct provider items, command executions, and file-change items;
- command categories such as inspection, test, verification, and proof validation;
- source, test, and audit-artifact change categories;
- the first source edit, first test command, first verification command, first audit
  artifact write, and first skill-proof write;
- the number of later provider items after selected milestones.

These fields sharpen ceremony and audit-tail analysis for Codex runs. With Codex
workspace checkpoints enabled, the runner now captures every distinct workspace state
at completed provider-item boundaries, evaluates those snapshots after the agent exits,
and reports:

- `first_functional_green_item` and `items_after_first_functional_green`;
- `first_bench_ready_green_item` and `items_after_first_bench_ready_green`;
- `functional_to_bench_ready_items`, which separates useful artifact completion from the
  broader post-functional tail;
- `checkpoint_coverage_complete`, which must be true before identifying the first
  evaluator-green captured provider item.

Snapshot evaluation happens after Codex exits so hidden checks do not steer the agent or
consume its context. The runner briefly pauses the Codex process group only while copying
a stable workspace snapshot and records that pause separately from evaluator time.

The resolution is a completed provider-item boundary followed by process-group pause. This
is the strongest observation available from the current Codex stream, but it is not an
instruction-level timestamp: a very small event-to-pause scheduling race remains possible.
Describe the result as the first evaluator-green captured provider item, and require
`checkpoint_coverage_complete=true` before treating it as the first observed green state.

Do not call all work after functional green "waste" automatically. For E arms, work
between functional green and bench-ready green may be required verification or proof.
Use the two tails separately and treat incomplete checkpoint coverage as non-conclusive.

## Interpretation

Use solution latency as a waste and stopping-behavior metric only when
`solution_latency_observable` is `true`.

If it is `false`, do not say the agent solved the task on a particular turn or provider
item. Say only that the final workspace was green and the first-green point was not
captured.
