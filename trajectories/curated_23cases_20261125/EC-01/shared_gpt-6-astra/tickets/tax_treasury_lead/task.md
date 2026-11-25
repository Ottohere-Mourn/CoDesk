# M&A Tax & Treasury Work Order — `tax_treasury_lead`

## Engagement Scope & Deliverables
Complete the closing Tax, FX breakage, unrestricted cash, and tax indemnity note schedule for Project Atlas in `/workspace/deal_model`.
The deal model `/workspace/deal_model/Merger_ProForma_2026.xlsx` is currently open in LibreOffice Calc on the workstation (with an active desk control tag in `QoE_Bridge!C1`) alongside the Virtual Data Room (VDR) session at `http://127.0.0.1:18801`.

Deliverables:
1. Reconcile closing Deferred Tax timing liabilities, IRC Section 382 NOL tax-asset offset, uncertain tax & Pillar-Two reserves, FX forward breakage, and Unrestricted Closing Cash (`USD_K`) from the full VDR CSV schedules (`http://127.0.0.1:18801`), scanned exhibits in `/workspace/deal_model/exhibits/`, and `/workspace/deal_model/SPA_Accounting_Policy.md`.
2. In the VDR (`FX_BASIS = SPOT_CLOSE_BS`, `TAB = TAX_ROLLFORWARD`), copy the VDR Tax Attestation Seal to the system clipboard and record it in `Tax_Deferred_Schedule!B8`; populate `Tax_Deferred_Schedule` (`B2:B5`, formula `=SUM(B2:B5)` in `B6`, and `Unrestricted_Closing_Cash_USD_K` in `B7`) in `Merger_ProForma_2026.xlsx`, preserving all existing sheets, cross-sheet formulas, and `QoE_Bridge!C1`.
3. Size only your tranche `Debt_Covenant_Model!B4` (`Tax_Indemnity_Note_USD_K`) within its facility bounds in `SPA_Accounting_Policy.md` so `Debt_Covenant_Model!B7` satisfies the closing Net Leverage covenant.
4. Save the completed workbook cleanly and export `/workspace/deal_model/Tax_Treasury_Pack.pdf` matching your finalized `Tax_Deferred_Schedule` and `Tax_Indemnity_Note_USD_K`. Keep `/workspace/deal_model` clean of scratch scripts or extra files (use `/tmp` for intermediate work).
