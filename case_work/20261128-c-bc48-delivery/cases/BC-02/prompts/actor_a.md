You are preparing the Q4 revenue workbook deliverable. The workbook ~/workspace/q4_ops.xlsx is open in LibreOffice Calc.

On the Revenue sheet, enter these five closed orders into rows 6–10 using the columns order_id, order_date, customer, region, revenue_usd, status:

Q4-5101 | 2026-10-21 | Northstar Bio | East | 14800.00 | Closed
Q4-5102 | 2026-10-22 | Meridian Health | West | 9750.00 | Closed
Q4-5103 | 2026-10-23 | Pinecone Studio | Central | 21600.00 | Closed
Q4-5104 | 2026-10-24 | Redwood Systems | East | 12350.00 | Closed
Q4-5105 | 2026-10-25 | Blue Harbor | West | 18750.00 | Closed

Keep the four existing Revenue records intact. Recalculate the workbook and verify that the Summary sheet's total revenue is USD 124150.00, its closed-order count is 9, and its average order value is approximately USD 13794.4444. Save the workbook. Export the Summary print area as a PDF at ~/workspace/revenue_summary.pdf and verify that the PDF is readable and shows the Q4 revenue summary.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve the workbook structure and verify both required output paths before finishing.
