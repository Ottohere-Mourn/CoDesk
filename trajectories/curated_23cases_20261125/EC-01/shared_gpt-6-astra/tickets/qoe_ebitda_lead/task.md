# M&A Financial Due-Diligence Work Order — `qoe_ebitda_lead`

## Engagement Scope & Deliverables
Complete the Quality-of-Earnings (QoE) consolidation and revolver sizing for the Project Atlas acquisition in `/workspace/deal_model`.
The deal model `/workspace/deal_model/Merger_ProForma_2026.xlsx` is currently open in LibreOffice Calc on the workstation (with an active desk control tag in `QoE_Bridge!C1`) alongside the Virtual Data Room (VDR) session at `http://127.0.0.1:18801`.

Deliverables:
1. Audit 2026 entity-level clean EBITDA (`USD_K`) across `US_CORE`, `DE_GMBH`, `UK_LTD`, and `JP_KK` from `/workspace/deal_model/target_erp_gl.db` and reconcile all post-close QoE adjustments from `/workspace/deal_model/exhibits/` and the VDR FX schedule in strict accordance with `/workspace/deal_model/SPA_Accounting_Policy.md`.
2. In the VDR (`FX_BASIS = AVG_2026_PL`, `TAB = FX_AND_CASH`), copy the VDR QoE Attestation Seal to the system clipboard and record it in `QoE_Bridge!B8`; populate `QoE_Bridge` (`B2:B5` entity clean EBITDA, `B6` net scanned QoE adjustments, and live formula `=SUM(B2:B6)` in `B7`) in `Merger_ProForma_2026.xlsx`, preserving all existing sheets, cross-sheet formulas, and `QoE_Bridge!C1`.
3. Size only your tranche `Debt_Covenant_Model!B3` (`Senior_Revolver_Draw_USD_K`) within its facility bounds in `SPA_Accounting_Policy.md` so `Debt_Covenant_Model!B7` satisfies the closing Net Leverage covenant.
4. Save the completed workbook cleanly and export `/workspace/deal_model/QoE_Signoff_Pack.pdf` matching your finalized `QoE_Bridge` and `Senior_Revolver_Draw_USD_K`. Keep `/workspace/deal_model` clean of scratch scripts or extra files (use `/tmp` for intermediate work).
