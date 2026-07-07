Benchmark arm: E — ai-engineering-skills.

Use the ai-engineering-skills plugin, not just wrapper prose.

Use the smallest native workflow that fits the task. Keep artifacts concise. For tiny bugfix tasks, prioritize the code fix before long artifacts.

A good default route for small bugfix tasks is:

bug-capture -> build-one -> verify-contract

Use additional skills only when they fit the task. Do not force a broad diagnostic loop for a one-line bug.

Useful namespaced skills include:
- /ai-engineering-skills:bug-capture
- /ai-engineering-skills:scope-freeze
- /ai-engineering-skills:build-one
- /ai-engineering-skills:test-mini
- /ai-engineering-skills:verify-contract
- /ai-engineering-skills:handoff

Create `SKILL_TRACE.jsonl` when using or skipping workflow skills. Keep it tiny: 2-5 JSONL rows is enough. Each line must be one JSON object with `event_type` and `skill_name`.

Allowed `event_type` values:
- `skill_available`
- `skill_considered`
- `skill_invoked`
- `skill_skipped`

This is agent-declared trace evidence, not runtime-hook proof. Do not let trace writing delay the implementation or verification work.

Required work order:
1. Read TASK.md before editing.
2. Make the smallest correct code change.
3. Create concise verification notes in VERIFY.md.
4. Create SKILL_RUNTIME_PROOF.md using the exact structure below.
5. Stop once TASK.md is complete and evidence is recorded.

Read .benchmark/SKILL_RUNTIME_CONTEXT.md before creating SKILL_RUNTIME_PROOF.md. Copy concrete values from that file. If it is missing, report the blocker instead of fabricating proof.

SKILL_RUNTIME_PROOF.md must use this exact structure and fill every field with concrete, non-placeholder values:

# Skill Runtime Proof

## Run
- Run ID: copy Run ID from .benchmark/SKILL_RUNTIME_CONTEXT.md
- Arm: copy Arm slug from .benchmark/SKILL_RUNTIME_CONTEXT.md
- Task: copy Task slug from .benchmark/SKILL_RUNTIME_CONTEXT.md
- Repeat: r1

## Skill source
- Repo URL: copy Repo URL from .benchmark/SKILL_RUNTIME_CONTEXT.md
- Pinned commit SHA: copy the exact 40-character lowercase SHA from .benchmark/SKILL_RUNTIME_CONTEXT.md
- Local path: copy Local plugin path from .benchmark/SKILL_RUNTIME_CONTEXT.md
- Install command: ./benchmark_harness/scripts/pin_skill_repos.sh local_plugins
- Install stdout/stderr path: benchmark-data/skill-repos/pinned_skill_repos.csv

## Activation
- Agent CLI: Claude Code
- Activation mechanism: namespaced skill invocation from pinned local plugin
- Prompt wrapper path: arms/E-ai-engineering-skills.md
- Agent-visible skill files: list the actual namespaced skills used
- Environment variables relevant to skill loading: CLAUDE_PLUGIN_DIR

## Pre-run availability check
- Command run: test -f .benchmark/SKILL_RUNTIME_CONTEXT.md
- Result: available
- Evidence path: .benchmark/SKILL_RUNTIME_CONTEXT.md

## During-run evidence
- Invocation evidence level: availability_only, artifact_inferred, agent_declared, or runtime_hook
- Did the agent mention or invoke the skill? yes/no/unclear: only say yes if SKILL_TRACE.jsonl or actual logs support it
- Evidence: list the namespaced skills or concise workflow used
- Notes: if shell verification is unavailable, say so; artifact evidence is not runtime-hook proof; external harness verification is authoritative

## Post-run caveat
- Could a bad result be due to the skill not being loaded? yes/no/unclear: no
- Reviewer notes: pinned skill context was present and copied into this proof

Do not leave placeholder values such as TBD, unknown, or blank fields in the final proof.

Run the proof validator before finishing if possible:

python -m benchmark_harness.validate_skill_runtime_proof SKILL_RUNTIME_PROOF.md

Complete TASK.md.
