# Work Order — DACH Statutory Impressum & DIN-1450 Font Release (`dach_legal_localization_lead`)

## Context & Objective
Prepare the German/Austrian/Swiss (DACH) statutory release package on this workstation. Review ``/workspace/specs/DACH_Statutory_Font_SOP.pdf``, the scanned regulatory & typographic exhibits in ``/workspace/specs/``, the open ``/workspace/DACH_Statutory_Impressum.odt`` document in LibreOffice Writer, and the authenticated **DACH Regulatory & Input Console** (`http://127.0.0.1:19501/dach-console`) in Chromium.

## Required Deliverables
1. **Updated ``/workspace/DACH_Statutory_Impressum.odt`` & exported ``/workspace/DACH_Statutory_Impressum.pdf``**:
   - Complete all mandatory German, Austrian, and Swiss statutory identifiers, conformity clauses, EU ODR dispute disclosure, and portal attestation code per the SOP and scanned extracts, purge all prohibited Anglo-American boilerplate clauses from the draft, preserve `[MANDATE-DACH-2026-Q4]`, and ensure the open LibreOffice Writer document and disk `.odt`/`.pdf` match.
2. **DIN-1450 Patched OpenType Font ``/workspace/fonts/DACHCorporateSans_DIN1450.ttf``**:
   - Starting from ``/workspace/fonts/DACHCorporateSans.ttf``, apply all vertical metric, proportional-flag, tabular numeral, and current 2026 DIN-1450 optical kerning updates from ``/workspace/specs/`` while preserving existing non-overridden kerning pairs in the base font.
3. **Compliance Summary ``/workspace/dach_localization_summary.json``**:
   - Record the structured audit summary following the schema in Section 4 of `DACH_Statutory_Font_SOP.pdf`.
