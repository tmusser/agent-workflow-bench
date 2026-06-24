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

Before finishing, create SKILL_RUNTIME_PROOF.md at the repo root that states:
- plugin: ai-engineering-skills
- invoked skills: list the ai-engineering-skills skills actually used
- proof: this run used the namespaced plugin skill commands above
- date/time

Keep the task-specific analysis restrained. Do not overclaim campaign lift.
