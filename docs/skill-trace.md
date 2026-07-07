# Skill Trace

`SKILL_TRACE.jsonl` is agent-declared trace evidence. It is useful, but it is not the
same thing as a true runtime-hook invocation log.

## Why Artifact Inference Is Not Enough

Durable artifacts such as `SPEC.md`, `VERIFY.md`, or `HANDOFF.md` can suggest that a
workflow skill was probably used. They cannot prove:

- that a specific skill command was invoked;
- which turn it happened on;
- whether the agent considered and skipped another skill first; or
- whether the artifact was produced by a wrapper, finalizer, or later continuation.

Artifact inference remains valuable, but it must stay clearly labeled as inference.

## Evidence Levels

The benchmark now separates four evidence levels:

| Level | Meaning |
| --- | --- |
| `availability_only` | The skill pack was visible or loadable, but there is no stronger routing or invocation evidence. |
| `artifact_inferred` | Durable artifacts align with a skill pattern, but there is still no direct routing trace. |
| `agent_declared` | The agent wrote explicit agent-declared trace evidence to `SKILL_TRACE.jsonl`. This is stronger than artifact inference, but still self-reported. |
| `runtime_hook` | Future work: a true runtime-integrated hook records turn-level skill invocation evidence. |

Only `runtime_hook` should be treated as true invocation proof.

## SKILL_TRACE.jsonl Schema

Each line must be one JSON object. Current supported event types:

- `skill_available`
- `skill_considered`
- `skill_invoked`
- `skill_skipped`

Required fields per row:

- `event_type`: one of the supported event types above
- `skill_name`: non-empty skill name string

Optional fields:

- `timestamp`
- `reason`
- `details`
- `run_id`
- `phase`

Example:

```jsonl
{"event_type":"skill_available","skill_name":"mini-spec"}
{"event_type":"skill_considered","skill_name":"verify-contract","reason":"verification artifact needed"}
{"event_type":"skill_invoked","skill_name":"verify-contract"}
{"event_type":"skill_skipped","skill_name":"handoff","reason":"no continuation needed"}
```

Malformed rows, blank lines, and unknown `event_type` values are counted as invalid.

## How To Interpret Agent-Declared Traces

`SKILL_TRACE.jsonl` improves on artifact inference because it can show:

- which skills were available;
- which skills were considered;
- which skills the agent says it invoked; and
- which skills it explicitly skipped.

That still does not make it a runtime-hook trace. The file is written by the agent or
wrapper layer, so it is self-declared evidence. Use it as a stronger routing signal than
artifact inference, not as proof of turn-level invocation.

Artifact alignment means the declared skill is consistent with produced artifacts. It
does not mean the declared skill definitely caused the artifact.

## Why This Is Not Yet Runtime-Hook Tracing

True runtime-hook tracing would need instrumentation at skill execution time, tied to the
actual runtime path, not just a workspace artifact the agent can write. Until that exists,
the benchmark should stay conservative:

- artifact summaries stay artifact-inferred;
- `SKILL_TRACE.jsonl` stays agent-declared;
- generated proof files must not claim `runtime_hook` unless a real hook produced the evidence.
