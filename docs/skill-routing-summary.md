# Skill Routing Summary

Skill routing summary is a deterministic post-run evidence summary.

It answers a narrow question:

> Which workflow skills are suggested by durable artifacts left in the workspace?

It does **not** prove that a slash command was invoked, that a skill fired at a
specific turn, or that private reasoning used a skill. The output uses inferred
language on purpose.

## Claim Boundary

Every summary includes this boundary:

```json
{
  "claim_boundary": "inferred_from_artifacts_not_runtime_invocation_trace"
}
```

That boundary is the feature. It prevents artifact evidence from being promoted
into a stronger runtime trace claim.

## Evidence Mapping

The first version uses a small static mapping:

| Inferred skill | Evidence files |
| --- | --- |
| `mini-spec` | `SPEC.md` |
| `thin-plan` | `PLAN.md`, `TODO.md` |
| `verify-contract` | `VERIFY.md` |
| `handoff` | `HANDOFF.md` |
| `bug-capture` | `BUGS.md` |
| `diagnose-loop` | `BUGFIX_REVIEW.md`, `FRESH_SESSION_REVIEW.md` |
| `grill-with-docs-lite` | `DATA_AUDIT.md`, `TRUST_AUDIT.md` |

`SKILL_RUNTIME_PROOF.md` is summarized separately. If present, it is validated
with the existing skill-runtime proof validator.

## Usage

Summarize one repository directly:

```bash
python -m benchmark_harness.skill_routing_summary summarize \
  --repo benchmark-data/workspaces/${RUN_ID}/repo \
  --run-id "$RUN_ID" \
  --phase initial \
  --arm-slug E-ai-engineering-skills \
  --out benchmark-data/runs/${RUN_ID}/skill_routing_summary.json
```

Summarize a benchmark run phase:

```bash
python -m benchmark_harness.skill_routing_summary summarize-run \
  --run-id "$RUN_ID" \
  --phase initial \
  --arm-slug E-ai-engineering-skills
```

Multiple phases can be summarized in one command:

```bash
python -m benchmark_harness.skill_routing_summary summarize-run \
  --run-id "$RUN_ID" \
  --phase initial \
  --phase full \
  --phase stripped \
  --arm-slug E-ai-engineering-skills
```

Default output paths:

| Phase | Output |
| --- | --- |
| `initial` | `benchmark-data/runs/<RUN_ID>/skill_routing_summary.json` |
| `full` | `benchmark-data/resume-runs/<RUN_ID>_full/skill_routing_summary.json` |
| `stripped` | `benchmark-data/resume-runs/<RUN_ID>_stripped/skill_routing_summary.json` |

## Output Shape

```json
{
  "schema_version": 1,
  "run_id": "v07pilot_07-dashboard-export_E_r1",
  "phase": "initial",
  "arm_slug": "E-ai-engineering-skills",
  "claim_boundary": "inferred_from_artifacts_not_runtime_invocation_trace",
  "skill_runtime_proof": {
    "exists": true,
    "valid": true,
    "issues": []
  },
  "inferred_skills": {
    "verify-contract": {
      "present": true,
      "evidence": ["VERIFY.md"],
      "evidence_count": 1
    },
    "handoff": {
      "present": true,
      "evidence": ["HANDOFF.md"],
      "evidence_count": 1
    }
  },
  "summary": {
    "skills_inferred": 2,
    "skills": ["handoff", "verify-contract"],
    "evidence_level": "proof_valid_with_artifacts"
  }
}
```

## Evidence Levels

| Level | Meaning |
| --- | --- |
| `proof_valid_with_artifacts` | A valid `SKILL_RUNTIME_PROOF.md` exists and at least one mapped skill artifact is present. This still does not prove turn-level invocation. |
| `present` | Skill artifacts are present, but runtime proof is missing or invalid. |
| `proof_only` | Runtime proof exists, but no mapped skill artifacts are present. |
| `absent` | No runtime proof and no mapped skill artifacts. |

## Interpretation

Use this as a routing-evidence index for log excavation:

- It can show that a run produced artifacts associated with specific skills.
- It can separate runtime-proof failures from artifact-production failures.
- It can be joined with telemetry to ask when artifact evidence appeared by phase.

It should not be used as a claim that a specific skill was invoked at a specific
turn. Real turn-level tracing would need explicit runtime hooks in the skill pack.
