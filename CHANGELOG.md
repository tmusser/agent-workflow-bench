# Changelog

All notable changes to this repository are documented here.

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
