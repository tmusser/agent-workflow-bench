# Campaign Channel Normalization

The weekly acquisition dashboard is splitting the same campaign channel into multiple rows because source labels are not normalized consistently.

Product says channel labels should be normalized as follows:

- trim leading/trailing whitespace;
- lowercase labels;
- treat blank or missing labels as `unknown`.

Goal:
Fix the channel normalization so the weekly report groups equivalent channel labels together and existing report behavior remains intact.

Constraints:
- Keep the change focused.
- Do not edit fixture data to make the tests pass.
- Do not add external services, databases, dashboards, or new infrastructure.
- Run `VERIFY.sh` before finishing.

Expected result:
- `Email` and ` email ` are reported as one `email` row.
- `PAID_SEARCH` and `paid_search` are reported as one `paid_search` row.
- blank or missing labels are reported as `unknown`.
- The repository passes its required verification.
