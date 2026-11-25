# Work Order — Endoscope Working Standoff, Fiducial Framing Render & LED Thermal Qualification (`endoscope_optics_eng`)

## Context & Objective
Calibrate `Endoscope_Camera` and `Endoscope_Light` in ``/workspace/shared_docs/laparoscopic_workcell.blend`` (open in Blender 3.4 on the desktop) and render the illuminated endoscopic view per ``/workspace/SOP_Optics_60601.pdf`` and ``/workspace/exhibits/cannula_thermal_derating.png``.

## Deliverables
1. **Updated ``/workspace/shared_docs/laparoscopic_workcell.blend`` & Cycles Render ``/workspace/renders/endoscope_view.png``**:
   - Position and aim `Endoscope_Camera` (and `Endoscope_Light`) so camera-to-lesion standoff, 3-fiducial central safe-frame projection, and unobstructed line-of-sight hold without overwriting `LeftGrasper_Arm` or `RightBipolar_Arm`, then render `960x540` `renders/endoscope_view.png`.
   - Configure `Endoscope_Light['led_illuminator_w']` and `Endoscope_Light['status'] = 'COMMITTED'` within both the optical SNR floor and the coupled IEC 60601 intra-abdominal thermal ceiling.
   - Ensure the open Blender 3.4 workcell window on the desktop is synchronized with the saved `.blend` on disk (reload/revert or save in the open Blender session with zero unsaved dirty state).
2. **Shared DHF ``/workspace/shared_docs/Design_History_File.odt``**:
   - Append your optical framing and thermal signoff plus document control code while preserving existing DHF content and keeping the open LibreOffice Writer window synchronized with disk.
3. **Audit JSON ``/workspace/optics_framing_audit.json``**: Follow Section 3 of `SOP_Optics_60601.pdf`.
