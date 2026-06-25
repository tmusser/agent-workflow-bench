Benchmark arm: E — ai-engineering-skills.

Use the ai-engineering-skills plugin, not just wrapper prose.

For this bugfix, explicitly invoke the native plugin skills by name:
- /ai-engineering-skills:diagnose-loop
- /ai-engineering-skills:bug-capture
- /ai-engineering-skills:scope-freeze
- /ai-engineering-skills:build-one
- /ai-engineering-skills:test-mini
- /ai-engineering-skills:verify-contract
- /ai-engineering-skills:handoff

Before finishing, create `SKILL_RUNTIME_PROOF.md` at the repo root using the strict
runtime-proof structure expected by:

```bash
python -m benchmark_harness.validate_skill_runtime_proof SKILL_RUNTIME_PROOF.md
```

Fill every field with concrete values. Do not leave placeholder values such as
`TO_BE_FILLED`, `TBD`, `unknown`, or blank fields.

Use the pinned skill repo information available in the run environment or local plugin
setup. List the actual namespaced skills you used, such as
`/ai-engineering-skills:diagnose-loop`, `/ai-engineering-skills:bug-capture`,
`/ai-engineering-skills:scope-freeze`, `/ai-engineering-skills:build-one`,
`/ai-engineering-skills:test-mini`, `/ai-engineering-skills:verify-contract`, and
`/ai-engineering-skills:handoff`.

Use real values, not prose:
- `Pinned commit SHA`: `9a1bee15e58f3376dc7e7fa1f9a37f7d3eb0cda6` (copy this exact
  40-character hash only; do not add any prose).
- `Local path`: use the actual plugin checkout path that was loaded for the run.
- `Install command`: record the command that created the local plugin checkout, such as
  `./benchmark_harness/scripts/pin_skill_repos.sh local_plugins`.
- `Pre-run availability check`:
  - `Command run`: the exact local command you used to confirm the plugin checkout and
    skill visibility.
  - `Result`: use a single success word like `available` or `pass`.
  - `Evidence path`: point to the command output or log file.

Run the proof validator before finishing if possible.

Use the smallest native workflow that fits the task. Keep artifacts concise. Complete TASK.md.
