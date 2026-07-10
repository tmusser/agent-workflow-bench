# Changelog

All notable changes to this repository are documented here.

## [0.2.0] - 2026-07-10

### Added

- Provider-item observability for Codex command and file-change events.
- Evaluator-backed Codex first-functional-green and first-bench-ready-green checkpoints.
- Stable, deferred Claude workspace checkpoints with stream-JSON turn coverage.
- Explicit complete, partial, stable, and polling-fallback coverage metadata.
- Separate snapshot-pause and evaluator-overhead measurements.
- Provider capability rubric in `docs/capabilities.md`.

### Changed

- Claude and Codex checkpoint evaluators run after the agent process exits, preventing hidden-evaluator feedback from affecting the agent session.
- Claude and Codex resume phases select the resume-specific hidden evaluator.
- Scorecards expose provider-native first-green, post-green, and coverage fields.
- Evidence classification separates functional outcomes from artifact/proof outcomes.
- Codex proof validation is runner-aware.

### Claim boundary

v0.2.0 improves observability; it does not prove that one provider, workflow arm, or skill pack is broadly superior. Exact first-green claims require complete checkpoint coverage. Claude turns and Codex provider items remain different native units.

## [0.1.0] - 2026-06-24

### Added

- Task 4 impossible-churn benchmark with artifact/resume mechanism checks.
- Task 5 fake-data trust benchmark with a public-pass / hidden-fail stress task.
- Scorecard support for both `*-eval-bundle.tar.gz` and `*-initial-fail-bundle.tar.gz`.
- Explicit claim boundaries that avoid overclaiming broad agent superiority.
- E-arm runtime proof validation and workflow-artifact accounting.

### Changed

- Public identity updated to `Agent Workflow Bench`.
- Package metadata aligned with the public release name.
- Documentation expanded for release setup, CI, and contribution workflow.

### Notes

- PyPI publishing is deferred until the repository exposes a stable CLI and package-data story.
- Generated bundles and benchmark data remain out of source control.
