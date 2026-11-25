# ICU Ventilator Prone Triage, Renal Hydration & Shift Handover Work Order — `ventilator_renal_lead`

## Scope & Deliverables
Complete the 16-bed ARDS prone-positioning triage and renal hydration sizing in `/workspace/icu_round/ICU_Shift_Brief.odt` and `ICU_Round_Ledger.xlsx` (both open in LibreOffice with active session tags), using **BedsideWave Monitor**, the **ICU Rounding Portal** at `http://127.0.0.1:19504/`, and `/workspace/icu_round/Vent_Renal_Nomogram.png`.

Deliverables:
1. Under `VIEW = VENT_RENAL_SI` in the open Chromium ICU Portal, export `/home/user/Downloads/icu_round_feed.csv` and copy the Ventilator Renal Seal to the clipboard; inspect **BedsideWave Monitor** to exclude `VTACH!` alarm beds from active hydration and prone positioning.
2. Per `Vent_Renal_Nomogram.png`, compute `Renal_Hydration_Volume_mL` across the non-alarm beds, set `Fluid_Envelope!B3` and `Fluid_Envelope!B8` (Ventilator Renal Seal) in `ICU_Round_Ledger.xlsx`, and size only `Electrolyte_Buffer_B_mL` (`Fluid_Envelope!B5` in `[5, 60]`) so `Fluid_Envelope!B6` (`=SUM(B2:B5)`) lands in `[1900.0, 1908.0]` mL (preserving `Vaso_Orders!C1` and `B2, B4, B7`).
3. Update `ICU_Shift_Brief.odt` (preserving `ICU-WRITER-804`) to record `VTACH_BEDS`, `PRONE_ELIGIBLE_BEDS` (non-VTach beds with `PaO2_FiO2 < 180`), and the Ventilator Renal Seal, export `/workspace/icu_round/ICU_Shift_Brief.pdf`, and write `/workspace/icu_round/VENT_SUMMARY.json` (`vtach_hold_beds`, `prone_eligible_beds`, `renal_hydration_ml`, `vent_seal`).
