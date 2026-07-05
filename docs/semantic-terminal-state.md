# Semantic Terminal State

`terminal_reason` is a raw agent-run status such as `completed` or `max_turns`.
It is useful, but it is not the same thing as functional correctness.

A run can hit `max_turns` after leaving a correct patch that passes public and
hidden verification. A run can also report `completed` while merely asking for
permission to run verification. The semantic terminal-state classifier makes that
distinction explicit in scorecards.

## Scorecard Fields

The scorecard now includes per-stage raw and semantic terminal fields:

- `initial_terminal_reason`
- `initial_semantic_terminal_state`
- `full_resume_terminal_reason`
- `full_resume_semantic_terminal_state`
- `stripped_resume_terminal_reason`
- `stripped_resume_semantic_terminal_state`

## States

| State | Meaning |
| --- | --- |
| `done_verified` | The run completed, public + hidden checks are green, and the agent output claims verification was run. |
| `done_unverified` | The run completed and public + hidden checks are green, but the agent did not clearly claim it verified. |
| `asks_permission_to_verify` | The final output is shaped like a request for permission to run verification, even if the harness later verifies the workspace externally. |
| `max_turns_after_correct_fix` | The run hit the turn limit, but the final workspace passes public + hidden checks. |
| `max_turns_before_correct_fix` | The run hit the turn limit before reaching a public + hidden green workspace. |
| `wrong_fix` | The run changed files, but public or hidden verification failed. |
| `no_diff` | The run did not leave a patch and did not reach a green workspace. |
| `not_run` | The phase was intentionally not run, usually because an initial-fail bundle is not resume-ready. |
| `unknown` | The available artifacts are insufficient for a sharper classification. |

## Interpretation

Use these states alongside existing scorecard fields. They are heuristics, not a
replacement for public/hidden evaluator results.

The most important distinction is:

- functional outcome: did public and hidden verification pass?
- terminal shape: did the agent finish cleanly, ask to verify, or hit the turn limit?
- audit behavior: did the agent leave proof artifacts and verification claims?

This avoids treating all `max_turns` rows as failures and all `completed` rows as
equally strong successes.
