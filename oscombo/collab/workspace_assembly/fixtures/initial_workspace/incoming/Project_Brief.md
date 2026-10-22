# Project Aurora asset handoff

Prepare these four source files for delivery. Preserve file bytes exactly.

| ID | Source | Final path | Description |
|---|---|---|---|
| ATT-CHART-01 | `incoming/q3_chart_final.png` | `delivery/attachments/q3_revenue_chart.png` | Q3 revenue chart |
| ATT-TERMS-01 | `incoming/vendor_terms_final_v2.pdf` | `delivery/attachments/vendor_terms.pdf` | Vendor payment and delivery terms |
| ATT-STOCK-01 | `incoming/inventory_week42.csv` | `delivery/attachments/inventory_snapshot.csv` | Week 42 inventory snapshot |
| ATT-COMP-01 | `incoming/supplier_compliance_note.txt` | `delivery/attachments/compliance_summary.txt` | Supplier compliance summary |

The report will live at `delivery/Quarterly_Supply_Report.odt`; its links must be relative to that directory (for example, `attachments/vendor_terms.pdf`). Keep `incoming/README.md` and `archive/q2_baseline.txt` unchanged.
