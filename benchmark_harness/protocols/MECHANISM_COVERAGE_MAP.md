# Mechanism Coverage Map

| Thesis mechanism | Measured in v1 pilot? | How measured | Limitation |
|---|---:|---|---|
| Better initial diagnosis | Partially | Functional score, human review, logs, first patch target | Not causally isolated from general model behavior |
| Reduced scope creep | Yes, descriptively | Files changed, LOC, unrelated edits, human scope score | Stripped resume does not remove initial scope benefits |
| Better verification choice | Partially | Test quality, regression coverage, verification notes | All arms are told to run VERIFY.sh |
| Durable resume context | Yes | Full vs artifact-stripped resume comparison | Only after implementation is complete |
| Artifact usefulness | Narrowly | artifact_resume_delta | Only measures leftover resume context |
| Generic handoff prompting vs skill behavior | No in v1 | Add A2 arm later | Not included in pilot |
| Data/modeling assumption discipline | Yes in Task 5 | Fake-data analysis trust task | Bugfix task is not enough |
