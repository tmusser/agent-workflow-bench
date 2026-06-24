# v0.4.2 Pilot Run Protocol

## Scope

Run only:

```text
Task 4: Impossible Churn Regression
Arms A-F
2 repeats per arm
```

Task 5 is documented separately in `docs/task5.md` and can be exercised through
`tools/pilot_smoke.sh` when `TASK_SLUG=05-fake-data-analysis` is set.

Do not add Task 1, A2, Ralph Vault arms, or public-report generation.

## Prepare starter repo

For each run:

```bash
RUN_ID="v04pilot_04-bugfix_A_r1"
STARTER="tasks/04-impossible-churn/starter_repo"
WORK="benchmark-data/workspaces/$RUN_ID/repo"

python -m benchmark_harness.prepare_run_workspace \
  --starter-repo "$STARTER" \
  --dest-repo "$WORK" \
  --metadata-out "benchmark-data/runs/$RUN_ID/run_workspace_manifest.json"

cd "$WORK"
STARTER_COMMIT="$(git rev-parse HEAD)"

python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Render prompt

From the pilot root:

```bash
python -m benchmark_harness.render_prompt \
  --arm-wrapper arms/A-baseline.md \
  --task-prompt tasks/04-impossible-churn/starter_repo/TASK.md \
  --out benchmark-data/runs/$RUN_ID/prompt.md
```

The rendered prompt must contain only:

```text
common runner wrapper
arm wrapper
public TASK.md
```

Do not include assessment contracts.

## Skill runtime proof

For every non-baseline skill arm, fill:

```text
benchmark-data/runs/$RUN_ID/SKILL_RUNTIME_PROOF.md
```

Use `benchmark_harness/templates/SKILL_RUNTIME_PROOF_TEMPLATE.md`.

Validate the filled proof before scoring a non-baseline run:

```bash
python -m benchmark_harness.validate_skill_runtime_proof \
  benchmark-data/runs/$RUN_ID/SKILL_RUNTIME_PROOF.md
```

A bad run is not interpretable unless this file makes it clear whether the skill was installed, activated, and visible to the agent. Placeholder values such as `TO_BE_FILLED`, `TBD`, `TODO`, empty fields, or angle-bracket placeholders must fail validation.

## Initial run

Use the same Claude Code / Sonnet / Ralph settings for every arm:

```text
model: Sonnet
iterations: same for every run
wall-clock timeout: same for every run
network: disabled or local-only
starting workspace: clean copy of starter repo
```

Save:

```text
benchmark-data/runs/$RUN_ID/
  prompt.md
  stdout.txt
  stderr.txt
  ralph_logs/
  verification_final.txt
  git_status_final.txt
  diff_stat.txt
  diff.patch
  artifact_inventory.csv
  SKILL_RUNTIME_PROOF.md
```

After the agent run, always collect git evidence from the run workspace:

```bash
cd "benchmark-data/workspaces/$RUN_ID/repo"
git status --short > "../../../runs/$RUN_ID/git_status_final.txt"
git diff --stat HEAD > "../../../runs/$RUN_ID/diff_stat.txt"
git diff HEAD > "../../../runs/$RUN_ID/diff.patch"
```

## Required verification

`VERIFY.sh` is table stakes because every arm receives that instruction.

Functional scoring rewards whether it passes. Assessment checks are run outside the agent-visible starter repo.

Workflow-resume scoring rewards whether the agent makes verification durable and interpretable:

- records which command was run;
- records whether it passed or failed;
- preserves enough result detail for review;
- explains what remains unverified;
- connects verification to the task risk;
- leaves a fresh session able to rerun or interpret verification without rediscovery.


## Assessment checks

After the initial run and after each resume run, run assessment checks from outside the agent-visible workspace:

```bash
python -m benchmark_harness.evaluators.task4_hidden_evaluator \
  --repo benchmark-data/workspaces/$RUN_ID/repo \
  > benchmark-data/runs/$RUN_ID/hidden_evaluator_final.txt 2>&1
```

The assessment checks are not part of `VERIFY.sh` and must not be copied into the agent-visible run workspace.

## Full resume workspace

Create a clean full workspace after the initial run:

```bash
python -m benchmark_harness.create_resume_workspace \
  --source-repo benchmark-data/workspaces/$RUN_ID/repo \
  --dest-repo benchmark-data/resume-workspaces/$RUN_ID/full/repo \
  --metadata-dir benchmark-data/resume-workspaces/$RUN_ID/full/metadata \
  --condition full
```

The generated `resume_workspace_manifest.json` must be written under `.../full/metadata/`, not inside `.../full/repo/`.

## Artifact-stripped resume workspace

Create a clean artifact-stripped workspace before the resume run:

```bash
python -m benchmark_harness.create_resume_workspace \
  --source-repo benchmark-data/workspaces/$RUN_ID/repo \
  --dest-repo benchmark-data/resume-workspaces/$RUN_ID/stripped/repo \
  --metadata-dir benchmark-data/resume-workspaces/$RUN_ID/stripped/metadata \
  --condition artifact_stripped \
  --manifest tasks/04-impossible-churn/task_output_manifest.yml
```

Both `resume_workspace_manifest.json` and `stripped_artifacts_manifest.json` must be written under `.../stripped/metadata/`, not inside `.../stripped/repo/`.

The resume agent is not told which condition it receives. This is **condition-undisclosed**, not truly blinded, because the condition may be inferable from missing files.

## Artifact stripping order

Workflow artifact stripping happens only when creating the artifact-stripped resume workspace.

It must happen before the resume agent starts.

The stripping script must never run after the resume agent has produced outputs.

For Task 4, `BUGFIX_REVIEW.md` may be removed from the initial-run workspace when creating the stripped resume condition, but any `BUGFIX_REVIEW.md` created by the resume agent is a resume output and must not be stripped before scoring.

## Resume prompt

Use `benchmark_harness/protocols/FRESH_SESSION_PROMPT.md` exactly for both full and stripped resume conditions.

Do not disclose the condition.

## Scoring

Score separately:

```text
Functional score
Workflow-resume score
artifact_resume_delta
Initial-path evidence
Misleading artifact caps
```

Do not generate a public report in v0.4.2 pilot.
