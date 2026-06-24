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

Before finishing, create SKILL_RUNTIME_PROOF.md at the repo root that states:
- plugin: ai-engineering-skills
- invoked skills: list the ai-engineering-skills skills actually used
- proof: this run used the namespaced plugin skill commands above
- date/time

Use the smallest native workflow that fits the task. Keep artifacts concise. Complete TASK.md.
