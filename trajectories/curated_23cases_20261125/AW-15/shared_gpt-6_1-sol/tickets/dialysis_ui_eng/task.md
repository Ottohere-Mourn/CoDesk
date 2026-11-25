# Work Order — Hemodialysis Qt5 HMI Safety Engineer (`dialysis_ui_eng`)

Enforce IEC 60601-2-16 spin-box & emergency-touch safety bounds inside the live **Qt5 Designer** window (`dialysis_panel.ui` open on the desktop) and complete the 48-session `spKt/V` adequacy audit in `/workspace/dialysis_safety`:

1. Read `/workspace/dialysis_safety/specs/IEC60601_Dialysis_Spec.pdf`, query `/workspace/dialysis_safety/patient_runs.sqlite` (`hd_runs`), and inspect the **IEC 60601-2-16 Dialysis Portal** in Chromium (`http://127.0.0.1:19615`, `Overview` and `Acute ICU Hemodialysis` views).
2. In the open **Qt5 Designer** window (`/srv/studio_project/dialysis_panel.ui`, mounted read-only in your terminal for post-save verification), update `bloodFlowSpin`, `ufGoalSpin`, `heparinSpin`, `startHdBtn`, and `clampVenousBtn` to satisfy every widget safety range, step size, and minimum touch target specified in Section 1 of `IEC60601_Dialysis_Spec.pdf`, then save (`Ctrl+S`).
3. Filtering `hd_runs` to completed acute ICU hemodialysis sessions per specification, compute 3-decimal `mean_sp_ktv` and `adequate_run_ids` (sorted list), write `/workspace/dialysis_safety/ui_ktv_audit.json` (`cert_id`, `evaluated_run_count`, `mean_sp_ktv`, `adequate_run_ids`), and record `"ui_cert"` in `/workspace/dialysis_safety/release_gate.json` (preserving any sibling keys!).
