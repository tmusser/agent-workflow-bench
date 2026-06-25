# Product Brief: Activation Metric v2

## v1 legacy definition

- denominator: eligible external trial users whose `signup_at` falls in the report month;
- numerator: users in denominator with at least one qualifying activation event during the same report calendar month.

## v2 definition

- denominator: eligible external trial users whose `signup_at` falls in the report month;
- numerator: users in denominator with at least one qualifying activation event within 7 days of that user's `signup_at`;
- activation window is relative to signup, not report calendar month.

## Eligibility

- `user_type == "external"`;
- `is_test_account == false`;
- `plan_at_signup == "trial"`;
- `signup_at` is present and parseable.

## Qualifying activation event

- `event_name == "activation_completed"`;
- `event_at` is present and parseable;
- `event_at >= signup_at`;
- if `cancelled_at` exists, `event_at` must be before `cancelled_at`;
- for v2, `event_at < signup_at + 7 days`.

## Reporting schema

- `month`;
- `definition_version`;
- `eligible_users`;
- `activated_users`;
- `activation_rate`.

## Non-goals

- no dashboard, database, scheduler, analytics platform, or external service.
