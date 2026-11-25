# Multi-Breakpoint FinOps Responsive & Modal QA Work Order — `finops_viewport_auditor`

## Scope & Deliverables
Audit **GridFlow FinOps** at `http://127.0.0.1:19502/` in the workstation Chromium browser (`127.0.0.1:9222`) across four exact responsive viewports and both interactive policy modals.

Deliverables:
1. **Four Live Breakpoint PNG Captures (`/workspace/captures/`)**:
   - Resize and capture the live rendered GridFlow FinOps viewport (including its responsive `#bpRibbon` top bar) at four exact resolutions:
     - `/workspace/captures/vp_375x812.png` (`375 x 812`)
     - `/workspace/captures/vp_768x900.png` (`768 x 900`)
     - `/workspace/captures/vp_1024x768.png` (`1024 x 768`)
     - `/workspace/captures/vp_1440x900.png` (`1440 x 900`)
2. **FinOps QA Audit JSON (`/workspace/FINOPS_QA.json`)** with exact keys:
   - `"total_invoices"` (int), `"breached_count"` (int: invoices strictly exceeding their Tier SLA cap from the `?` SLA drawer), `"t1_disputed_ids"` (sorted list of disputed `T1` invoice IDs), `"breached_total_usd"` (float, 2 decimals)
   - `"fx_eur_usd_rate"` (float from `Ctrl+K` FX modal), `"mobile_375_overflow_px"` (int: horizontal overflow of `#wideHero` at `375px` width), `"mobile_approve_btn_height_px"` (int: rendered height of `#approveBtn`), and `"fx_modal_escape_closes"` (bool: whether `Escape` closes `#fxModal`).
