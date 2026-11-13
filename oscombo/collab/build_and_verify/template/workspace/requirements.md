# OrderDesk filter repair

The text field searches order ID, customer name and region with trimmed,
case-insensitive substring matching. The status selector and text query must
combine conjunctively. `All` removes the status constraint. Enter and the
Apply button must submit the same filter without navigating away. Clear resets
both controls. The result count is announced in the existing live region.

Use `tests/public_test_plan.json` for browser scenarios. The records in
`data/orders.json` are visible and may be inspected by both roles. Do not alter
fixture data, markup structure, styles, this requirement, or the test plan.
