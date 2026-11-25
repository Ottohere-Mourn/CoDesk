# Work Order — Hemodialysis Clinical Localization & TMP Engineer (`dialysis_l10n_eng`)

Complete all 8 German (`de_DE`) translations in the live **Qt5 Linguist** window (`dialysis_de.ts` open on the desktop) and complete the 48-session transmembrane pressure (`TMP`) safety audit in `/workspace/dialysis_safety`:

1. Read `/workspace/dialysis_safety/specs/IEC60601_Dialysis_Spec.pdf`, query `/workspace/dialysis_safety/patient_runs.sqlite` (`hd_runs`), and inspect the **IEC 60601-2-16 Dialysis Portal** in Chromium (`http://127.0.0.1:19615`, `Overview`, `Acute ICU Hemodialysis`, and `Approved de_DE Dialysis Glossary` views).
2. In the open **Qt5 Linguist** window (`/srv/studio_project/dialysis_de.ts`, mounted read-only in your terminal so you can verify with `lrelease` after saving), enter the exact approved German translation for all 8 `DialysisPanel` entries, mark each translation Done (`Ctrl+Return`), and save (`Ctrl+S`).
3. Filtering `hd_runs` to completed acute ICU hemodialysis sessions per specification, compute oncotic-adjusted transmembrane pressure (`tmp_mmhg`, 1 decimal) for each eligible session, write `/workspace/dialysis_safety/tmp_l10n_audit.json` (`cert_id`, `evaluated_run_count`, `max_tmp_mmhg`, `alarm_triggered_runs`), and record `"l10n_cert"` in `/workspace/dialysis_safety/release_gate.json` (preserving any sibling keys!).
