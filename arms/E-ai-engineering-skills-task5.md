Benchmark arm: E — ai-engineering-skills (Task 5).

Use the ai-engineering-skills plugin, not just wrapper prose.

For this fake-data trust task, explicitly invoke the native plugin skills by name:
- /ai-engineering-skills:mini-spec
- /ai-engineering-skills:scope-freeze
- /ai-engineering-skills:verify-contract
- /ai-engineering-skills:handoff
- optionally /ai-engineering-skills:bug-capture
- optionally /ai-engineering-skills:diagnose-loop

Audit the dataset before writing any summary. Prefer structured outputs, cautious language,
and a concise verification trail that another session can resume from.

Before finishing, create `SKILL_RUNTIME_PROOF.md` at the repo root using the strict
runtime-proof structure expected by:

```bash
python -m benchmark_harness.validate_skill_runtime_proof SKILL_RUNTIME_PROOF.md
```

Fill every field with concrete values. Do not leave placeholder values such as
`TO_BE_FILLED`, `TBD`, `unknown`, or blank fields.

Use the pinned skill repo information available in the run environment or local plugin
setup. List the actual namespaced skills you used, such as
`/ai-engineering-skills:mini-spec`, `/ai-engineering-skills:scope-freeze`,
`/ai-engineering-skills:verify-contract`, `/ai-engineering-skills:handoff`,
`/ai-engineering-skills:bug-capture`, and `/ai-engineering-skills:diagnose-loop`.

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

Keep the task-specific analysis restrained. Do not overclaim campaign lift.
