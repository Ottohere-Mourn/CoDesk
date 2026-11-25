# PCB Thermal Derating & Power Envelope Work Order — `thermal_power_eng`

## Scope & Deliverables
Complete the 8-zone VRM thermal derating in `/workspace/gateway/Board_Thermal_BOM.xlsx` (open in LibreOffice Calc with active desk tag in `VRM_Zones!C1`) and `/workspace/gateway/power_thermal_cfg.json`, using **IRCam PCB Analyzer** and the **Hardware Compliance Portal** at `http://127.0.0.1:19505/`.

Deliverables:
1. Inspect **IRCam PCB Analyzer** (`Ctrl+P` Preferences) on the desktop to identify all white-hot/red hotspot zones (`>=92C`) and required `fan_pwm_duty_pct`; under `MODE = VRM_THERMAL_SPEC` in the open Chromium portal, export `/home/user/Downloads/board_compliance.csv` and copy the VRM Thermal Seal to the clipboard.
2. Update `/workspace/gateway/power_thermal_cfg.json` (`hotspot_zones` sorted list, `fan_pwm_duty_pct`, `vrm_derated_rail_w`, `vrm_seal`) so live `GET http://127.0.0.1:19515/status` serves the updated thermal config.
3. Populate `VRM_Zones` (`A2:D9`, preserving `VRM_Zones!C1`) and `Power_Envelope!B2` (`VRM_Derated_Rail_W`), `B7` (`VRM_Thermal_Seal`), and size `Thermal_Guardband_A_W` (`B4` in `[0.5, 6.0]`) so `Total_Board_Power_W` (`B6`, formula `=SUM(B2:B5)`) lands in `[190.0, 190.8]` W while keeping Calc in sync, and export `/workspace/gateway/Thermal_Report.pdf`.
