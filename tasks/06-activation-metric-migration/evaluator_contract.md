# Task 6 Hidden Evaluator Contract

This file is not part of the public starter repo shown to agents. It documents the hidden evaluator at a high level for benchmark maintainers.

The hidden evaluator checks functional metric behavior on private fixtures. It does not require workflow artifacts for hidden correctness.

## Hidden Checks

- v1 API is preserved.
- v1 private expected behavior is preserved.
- v2 denominator is eligible external trial signups in the report month.
- v2 numerator is unique users with a qualifying activation within 7 days of signup.
- The activation window is signup-relative.
- An activation in the next month can count for the previous signup month when it is within 7 days.
- An activation in the report month does not count if the signup is outside the report month.
- Duplicate activation events count once per user.
- Internal and test users are excluded.
- Invalid signup values are excluded.
- Pre-signup events are ignored.
- Activation after cancellation is ignored.
- `current_plan` and other post-signup plan fields do not control the denominator.
- The report includes `definition_version`.
- A zero-denominator month returns `eligible_users=0`, `activated_users=0`, `activation_rate=0.0`.
