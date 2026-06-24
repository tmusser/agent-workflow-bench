# Version

Benchmark repo name: `agent-workflow-bench`

Package version: `0.1.0`

Release label:

```text
Agent Workflow Bench: Task 4 harness + artifact-resume mechanism test
```

Scope exclusions:

```text
No Task 1
No Task 5
No A2 no-skill + explicit handoff arm
No Ralph Vault arms
No public-report generator
No fabricated benchmark results
```

v0.4.2 blocker fixes:

```text
Metadata outside agent-visible resume repos
Git baseline initialized in every run workspace
Public tests/checks no longer expose hidden root-cause criteria
Assessment checks moved outside starter repo
Fixture coverage requires active-interval mapping
Skill runtime proof strict validation rejects placeholders
Private active-interval checks reject both first-plan-wins and last-plan-wins mistakes
Starter repo `.gitignore` suppresses venv/cache/build noise
```

Current pilot lineage:

```text
This repository still carries the v0.4.2 pilot task design and scoring lineage, but its public
identity is Agent Workflow Bench.
```
