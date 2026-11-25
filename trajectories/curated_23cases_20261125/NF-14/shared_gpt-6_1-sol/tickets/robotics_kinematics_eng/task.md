# Work Order — Articulated Instrument Organ-Clearance & Bipolar Duty Qualification (`robotics_kinematics_eng`)

## Context & Objective
Resolve anatomical collisions and sightline interference for `LeftGrasper_Arm` and `RightBipolar_Arm` in ``/workspace/shared_docs/laparoscopic_workcell.blend`` (open in Blender 3.4 on the desktop) per ``/workspace/SOP_Kinematics_60601.pdf`` and ``/workspace/exhibits/cannula_thermal_derating.png``.

## Deliverables
1. **Updated ``/workspace/shared_docs/laparoscopic_workcell.blend``**:
   - Reposition/orient `LeftGrasper_Arm` and `RightBipolar_Arm` so all organ keep-out surface clearances, inter-arm shaft separation, target lesion working reach, and optical corridor non-occlusion rules in Section 1 of the SOP hold without clobbering `Endoscope_Camera` or `Endoscope_Light`.
   - Configure `RightBipolar_Arm['bipolar_duty_w']` and `RightBipolar_Arm['status'] = 'COMMITTED'` within both the hemostasis floor and the coupled IEC 60601 intra-abdominal thermal ceiling.
   - Ensure the open Blender 3.4 workcell window on the desktop is synchronized with the saved `.blend` on disk (reload/revert or save in the open Blender session with zero unsaved dirty state).
2. **Shared DHF ``/workspace/shared_docs/Design_History_File.odt``**:
   - Record your kinematics verification summary and document control code while preserving existing DHF headers/sections and keeping the open LibreOffice Writer window synchronized with disk.
3. **Audit JSON ``/workspace/kinematics_clearance_audit.json``**: Follow Section 3 of `SOP_Kinematics_60601.pdf`.
