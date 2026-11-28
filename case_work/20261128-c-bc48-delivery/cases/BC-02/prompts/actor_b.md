You are preparing the Q4 expense workbook deliverable. The workbook ~/workspace/q4_ops.xlsx is open in LibreOffice Calc.

On the Expenses sheet, correct approved_cost_usd in rows 2–6 to these amounts while preserving the department, month, cost center, and voucher totals:

Sales | 18300.00
Research | 42600.00
Operations | 21750.00
Support | 12800.00
Security | 15300.00

In share_of_total cells F2:F6, enter a formula for each row equal to that row's approved_cost_usd divided by the sum of approved_cost_usd in E2:E6. Use formulas that recalculate when values change; do not replace them with fixed percentages. Format the share column as percentages, recalculate, and verify the approved-cost total is USD 110750.00 and the shares total 100%. Save the workbook. Export the Expenses sheet as a readable PDF at ~/workspace/expense_summary.pdf and verify that all five departments, approved costs, and shares are visible.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve the workbook structure and verify both required output paths before finishing.
