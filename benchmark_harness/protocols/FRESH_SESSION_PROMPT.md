# Fresh Session Prompt: Task 4 v0.4.2 Pilot

You are a fresh agent session in a benchmark.

You do not have access to the previous chat, prior Ralph logs, benchmark prompts, scoring metadata, or transcripts. Use only the current workspace state: TASK.md, source files, tests, task outputs, and any durable artifacts left in the repository.

Do not edit code yet.

First-pass review:
- Read up to 5 files before writing section 1 of FRESH_SESSION_REVIEW.md if possible.
- Prefer files that appear intended to help a future session, if any exist.
- If you need more than 5 files, continue only after recording why the additional file is necessary.

Write FRESH_SESSION_REVIEW.md section 1 with:
- files read first;
- any additional files read and why;
- what you believe the previous session completed;
- what remains uncertain or risky;
- the first verification command you will run;
- whether the repository contains enough durable context to resume without rediscovery.

After section 1:
1. Run the required verification from VERIFY.sh, or explain exactly why it cannot run.
2. Complete this small resume request:

   Write BUGFIX_REVIEW.md explaining the root cause of the March enterprise churn issue, why the fix is not merely a superficial dashboard-display fix, and which command proves regression coverage. If no regression test exists for the root cause, add one.

3. Keep the change small.
4. Update FRESH_SESSION_REVIEW.md with:
   - verification commands and results;
   - the change made;
   - files changed;
   - remaining uncertainty;
   - missing, stale, or misleading context;
   - whether prior artifacts reduced rediscovery.
