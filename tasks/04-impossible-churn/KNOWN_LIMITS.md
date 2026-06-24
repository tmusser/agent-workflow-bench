# Known limits of v1 pilot

This v1 pilot tests harness reliability and fresh-session resume behavior on one bugfix task.

It does not prove broad benchmark performance across high-ceremony coding tasks.

The artifact-stripped control measures resume-context value after implementation is complete. It does not isolate the full causal value of workflow gates during initial implementation, such as avoiding wrong fixes, reducing scope creep, choosing better verification, or preventing overbuild.

Task 4 may be reconstructable from code, tests, and diffs alone. A small artifact_resume_delta on Task 4 does not falsify the broader thesis. It may mean this task is not artifact-sensitive enough for the resume-control mechanism.

Public proof requires adding at least one artifact-sensitive data/modeling task after the harness pilot.

The v1 pilot should be reported as:

```text
Task 4 harness pilot + artifact-resume mechanism test
```

not as:

```text
benchmark proof that artifacts help
```
