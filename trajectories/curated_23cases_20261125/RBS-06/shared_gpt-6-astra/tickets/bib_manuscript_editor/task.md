# Systematic Review Curation & BibTeX Remediation Work Order — `bib_manuscript_editor`

## Scope & Deliverables
Curate the 20-study literature database in `/workspace/meta_review/citevault.sqlite`, clean the BibTeX bibliography, and finalize `Survey_Manuscript.odt`.
Both `/workspace/meta_review/Survey_Manuscript.odt` (with an active session tag `SURVEY-DESK-806`) and `Evidence_Synthesis.xlsx` (with an active session tag in `Study_Weights!C1`) are open in LibreOffice alongside the Preprint & Retraction Registry at `http://127.0.0.1:19306/`.

Deliverables:
1. Under `VIEW = RETRACTION_WATCH` on `http://127.0.0.1:19306/`, export `/home/user/Downloads/registry_feed.csv` and copy the Editorial Retraction Seal to the clipboard.
2. Update `citevault.sqlite` table `studies`: set `curation_status = 'INCLUDED_ELIGIBLE'` for all `ELIGIBLE_PRIMARY` studies (`16` studies) and `'EXCLUDED_RETRACTED'` for all retracted/superseded studies (`4` studies).
3. Write `/workspace/meta_review/references_clean.bib` containing `@article{<bib_key>, ...}` entries (with `author`, `year`, and `doi` fields) for **only** the `16` eligible primary studies.
4. Record the Editorial Retraction Seal in `Evidence_Synthesis.xlsx` cell `Pooled_Summary!B7` (preserving all other sheets, formulas, and `Study_Weights!C1`), update `Survey_Manuscript.odt` so it contains `INCLUDED_STUDIES=16`, `EXCLUDED_RETRACTED=4`, the Editorial Retraction Seal, and the active `SURVEY-DESK-806` tag, and export `/workspace/meta_review/Survey_Manuscript.pdf`.
