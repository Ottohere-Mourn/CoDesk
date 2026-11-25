# Biostatistics Inverse-Variance Meta-Analysis Work Order — `evidence_quant_analyst`

## Scope & Deliverables
Complete the 16-study inverse-variance fixed-effect meta-analysis in `/workspace/meta_review/Evidence_Synthesis.xlsx` and render the forest plot.
Both `/workspace/meta_review/Evidence_Synthesis.xlsx` (with an active session tag in `Study_Weights!C1`) and `Survey_Manuscript.odt` are open in LibreOffice alongside `http://127.0.0.1:19306/`.

Deliverables:
1. Under `VIEW = COHORT_EFFECT_SIZES` on `http://127.0.0.1:19306/`, export `/home/user/Downloads/registry_feed.csv` (cross-checking against `RETRACTION_WATCH` / `citevault.sqlite` so the 4 retracted/superseded studies `ST-04, ST-09, ST-14, ST-18` are **excluded**) and copy the Biostatistics Synthesis Seal to the clipboard.
2. Populate `Evidence_Synthesis.xlsx`:
   - In `Study_Weights`: list the `16` eligible studies in `A2:D17` with `w_i = 1 / se_i^2` in col `B` and `w_i * log_rr_i` in col `D`, preserving the active desk tag in `Study_Weights!C1`.
   - In `Pooled_Summary`: set `B2 = 16`, `B3 = sum(w_i)`, `B4 = sum(w_i * log_rr_i)`, formula `=B4/B3` in `B5` (`Pooled_FixedEffect_LogRR`), and the Biostatistics Synthesis Seal in `B6` (preserving `B7`).
3. Render a clean forest plot PNG (`>= 800 x 480` px) to `/workspace/meta_review/forest_plot.png` and export `/workspace/meta_review/Evidence_Summary.pdf` from `Evidence_Synthesis.xlsx`.
