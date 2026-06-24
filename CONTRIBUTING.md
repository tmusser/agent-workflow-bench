# Contributing

Thanks for helping improve Agent Workflow Bench.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Tests

Run the release test suite before sending changes:

```bash
python -m pytest benchmark_harness/tests -q
```

If you change the scorecard or bundle handling, also run a representative scorecard command against local bundles.

## Adding a Task

When adding a task, keep the benchmark structure consistent:

1. Create a new `tasks/<slug>/starter_repo/` with a public `TASK.md`, `README.md`, and `VERIFY.sh`.
2. Add a hidden evaluator under `benchmark_harness/evaluators/`.
3. Add tests for both expected success and expected failure paths.
4. Keep the hidden contract out of the agent-visible starter prompt.
5. Update scorecard, task catalog, and docs if the task changes bundle behavior or reporting.

## Hidden Evaluator Guidelines

- Keep evaluator logic private to the harness.
- Test positive and negative examples explicitly.
- Prefer conservative claim detection over permissive matching.
- Do not leak hidden trap details into the public task prompt or starter repo.
- If a rule depends on a generated artifact, add a deterministic test for it.

## Hygiene

Do not commit:

- `benchmark-data/`
- `local_plugins/`
- `*.tar.gz`
- `.venv/`
- `*.egg-info/`
- `__pycache__/`
- `.pytest_cache/`
- starter repo `outputs/` directories

## Release Note

PyPI publishing is deferred until the repo exposes a stable CLI and package-data story.
