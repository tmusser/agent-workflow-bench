# E-arm Audit Finalizer

You are running the E-arm audit finalizer.

The functional solution is already complete. Do not change functional code,
tests, fixtures, task data, or benchmark harness code.

Your only job is to make the run bench-ready by producing the required audit
artifacts.

## Hard restrictions

- Create or edit exactly these files only:
  - `SKILL_RUNTIME_PROOF.md`
  - `VERIFY.md`
- Do not edit `src/`, `tests/`, `fixtures/`, task data, or benchmark harness code.
- Do not run shell commands.
- Do not ask for command approval.
- Do not claim that you validated the proof yourself.
- The benchmark harness will validate `SKILL_RUNTIME_PROOF.md`, rerun
  `VERIFY.sh`, and rerun the hidden evaluator after you finish.

## Required source

Read `.benchmark/SKILL_RUNTIME_CONTEXT.md` before writing proof. Use concrete
values from that file, the visible prompt/task files, and the workspace.

Do not leave any required field blank. Do not use placeholder values such as
`unknown`, `unavailable`, `TBD`, `TO_BE_FILLED`, or `not provided`.

## Required SKILL_RUNTIME_PROOF.md shape

Create `SKILL_RUNTIME_PROOF.md` with this exact heading and field structure:

```md
# Skill Runtime Proof

## Run
- Run ID:
- Arm:
- Task:
- Repeat:

## Skill source
- Repo URL:
- Pinned commit SHA:
- Local path:
- Install command:
- Install stdout/stderr path:

## Activation
- Agent CLI:
- Activation mechanism:
- Prompt wrapper path:
- Agent-visible skill files:
- Environment variables relevant to skill loading:

## Pre-run availability check
- Command run:
- Result:
- Evidence path:

## During-run evidence
- Did the agent mention or invoke the skill? yes/no/unclear:
- Evidence:
- Notes:

## Post-run caveat
- Could a bad result be due to the skill not being loaded? yes/no/unclear:
- Reviewer notes:

Fill every field with a concrete, non-placeholder value.

For fields that refer to evidence, use concrete local paths such as
.benchmark/SKILL_RUNTIME_CONTEXT.md, SPEC.md, VERIFY.md, HANDOFF.md,
or the prompt wrapper path named in the runtime context.

For Result, use a single concrete success word such as available or pass
when the runtime context shows the skill was available.

For During-run evidence, cite visible evidence from the run workspace, such as
SPEC.md, VERIFY.md, HANDOFF.md, prompt wrapper instructions, or other
agent-created files. If the main agent did not create all expected artifacts,
state that clearly without using placeholder language.

Required VERIFY.md shape

Create or update VERIFY.md with a compact note:

The finalizer did not run commands.
The main run reached functional green before this finalizer was eligible.
The harness will rerun VERIFY.sh, the hidden evaluator, and the proof
validator after the finalizer exits.
SKILL_RUNTIME_PROOF.md was created for harness validation.
Final response

After writing the files, respond briefly that the two audit artifacts were
created. Do not ask to run commands.
