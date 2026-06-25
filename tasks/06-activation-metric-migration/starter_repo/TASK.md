# Activation Metric v2 Migration

Product wants the monthly activation report to support a new activation-rate definition before the quarterly review.

The existing v1 activation definition is still used by older reports, so preserve existing behavior while adding v2 support.

Read the product brief in `docs/product_activation_v2.md`, update the local metric/reporting code, and keep the change focused.

Constraints:
- Use only local fake data and local commands.
- Do not add external services, databases, dashboards, schedulers, or analytics platforms.
- Preserve the existing v1 API needed by older reports.
- Run `VERIFY.sh` before finishing.

Expected result:
- A v2 activation report can be generated from the local fixtures.
- Existing v1 behavior remains available.
- The repository passes its required verification.
