# Support SLA Boundary Regression

The weekly support dashboard is counting tickets answered exactly at the SLA deadline as breaches.

Product says a first response is on time when it arrives before or exactly at the SLA threshold:

- urgent tickets: 4 hours
- standard tickets: 24 hours

Goal:
Fix the SLA breach calculation so exact-boundary responses are not counted as breaches and existing report behavior remains intact.

Constraints:
- Keep the change focused.
- Do not edit fixture data to make the tests pass.
- Do not add external services, databases, dashboards, or new infrastructure.
- Run `VERIFY.sh` before finishing.

Expected result:
- The exact-boundary tickets are classified as on time.
- Tickets beyond the threshold are still classified as breaches.
- The repository passes its required verification.
