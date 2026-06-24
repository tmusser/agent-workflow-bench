# Skill Arm Setup

This guide shows how to prepare the `ai-engineering-skills` workflow pack for the E arm.

## 1. Create the local plugin checkout

The benchmark expects a machine-local checkout at `local_plugins/ai-engineering-skills`.
`local_plugins/` is ignored on purpose because it is a private, machine-specific install
location for third-party skill code, not benchmark source.

Create it with the public default URL:

```bash
./benchmark_harness/scripts/pin_skill_repos.sh local_plugins
```

That command writes `local_plugins/ai-engineering-skills` and records pinned skill
metadata in `local_plugins/pinned_skill_repos.csv`.

If you need to test a private fork, override the repo URL:

```bash
AI_ENGINEERING_SKILLS_REPO_URL=https://github.com/<owner>/<repo>.git \
  ./benchmark_harness/scripts/pin_skill_repos.sh local_plugins
```

If you want to use the current public skill repo directly, this also works:

```bash
AI_ENGINEERING_SKILLS_REPO_URL=https://github.com/tmusser/ai-engineering-skills.git \
  ./benchmark_harness/scripts/pin_skill_repos.sh local_plugins
```

## 2. Run the E arm

Use the local plugin checkout when running the E arm:

```bash
TASK_SLUG=04-impossible-churn \
ARM_SLUG=E-ai-engineering-skills \
RUN_ID=v04pilot_04-bugfix_E_r1 \
CLAUDE_PLUGIN_DIR="$PWD/local_plugins/ai-engineering-skills" \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_MAX_TURNS=60 \
./tools/pilot_smoke.sh auto-a-r1
```

For Task 5:

```bash
TASK_SLUG=05-fake-data-analysis \
TASK_ID=05-fake-data \
ARM_SLUG=E-ai-engineering-skills \
RUN_ID=v05pilot_05-fake-data_E_r1 \
CLAUDE_PLUGIN_DIR="$PWD/local_plugins/ai-engineering-skills" \
CLAUDE_PERMISSION_MODE=acceptEdits \
CLAUDE_MAX_TURNS=60 \
./tools/pilot_smoke.sh auto-a-r1
```

## 3. Validate runtime proof

The benchmark does not treat the presence of `SKILL_RUNTIME_PROOF.md` as enough.
The proof is validated with the harness validator:

```bash
python -m benchmark_harness.validate_skill_runtime_proof \
  benchmark-data/workspaces/$RUN_ID/repo/SKILL_RUNTIME_PROOF.md
```

That validator checks for the required markers, non-placeholder fields, and a real
pre-run availability result. If the proof is invalid, the run should not be treated as
runtime-proven.

## 4. Why this is documented separately

The E arm is reproducible, but the skill repository itself is external to the benchmark
source. Keeping the setup here avoids burying the installation step inside task text and
makes it clear how the runtime proof connects the installed plugin to the observed run.
