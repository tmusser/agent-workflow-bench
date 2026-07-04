# Product Refund Grain Regression

The weekly commerce dashboard is overcounting refunded orders when one order has multiple refund events.

Product says refund rate is order-based:

```text
refunded_orders / total_orders
```

A partially refunded order and a fully refunded order both count as one refunded order. Multiple refund events for the same order must not count multiple times.

Goal:
Fix the product refund-rate calculation so each refunded order is counted once per product and existing report behavior remains intact.

Constraints:
- Keep the change focused.
- Do not edit fixture data to make the tests pass.
- Do not add external services, databases, dashboards, or new infrastructure.
- Run `VERIFY.sh` before finishing.

Expected result:
- Duplicate refund events for one order count as one refunded order.
- Products with different refund rates remain separated.
- The repository passes its required verification.
