# Mechanical & Thermal Engineering Work Order — `mech_thermal_eng`

## Scope & Deliverables
Complete the Rev-C top ventilation lid machining and thermal schedule for the 1U telecom chassis in `/workspace/enclosure_revC`.
The BOM/compliance workbook `/workspace/enclosure_revC/Thermal_EMI_BOM.xlsx` is currently open in LibreOffice Calc on the workstation (with an active ECN control tag in `Thermal_Vent_Schedule!C1`) alongside the Hardware PLM Portal at `http://127.0.0.1:18803`.

Deliverables:
1. Review `/workspace/enclosure_revC/Engineering_Standard_IEC.md`, scanned mechanical keepout drawing `/workspace/enclosure_revC/scans/top_lid_keepout_revC.png`, and the Hardware PLM Portal (`http://127.0.0.1:18803`).
2. Machine ventilation through-cutouts on solid `TopVentCover` in `/workspace/enclosure_revC/chassis_housing.FCStd` meeting all thermal dissipation, structural area, outer gasket keepout, and central heatsink boss keepout requirements while preserving all other solids, and export the complete multi-solid assembly to `/workspace/enclosure_revC/release/chassis_housing.step`.
3. In the PLM Portal (`DISCIPLINE = THERMAL_CFD`, `UNIT_SYSTEM = IEC_60297_METRIC_MM`), export the metric 14-item feature catalog CSV and copy the Thermal ECN Sign-Off Seal to the system clipboard for `Thermal_Vent_Schedule!B5`; populate `Thermal_Vent_Schedule!B2:B4` and size only `Joint_Compliance!B2` (`Top_Cover_Torque_Spec_Ncm`) so `Joint_Compliance!B4` satisfies the frame preload specification, preserving all sheets, formulas, and `Thermal_Vent_Schedule!C1`. Keep `/workspace/enclosure_revC` clean of scratch scripts or extra files (use `/tmp` for intermediate work).
