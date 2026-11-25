# ICU Vasopressor Titration & Fluid Carrier Work Order — `vasopressor_pharmacist`

## Scope & Deliverables
Complete the 16-bed vasopressor titration in `/workspace/icu_round/ICU_Round_Ledger.xlsx` (open in LibreOffice Calc with active desk tag in `Vaso_Orders!C1`, alongside `ICU_Shift_Brief.odt`), using **BedsideWave Monitor**, the **ICU Rounding Portal** at `http://127.0.0.1:19504/`, and `/workspace/icu_round/Vaso_Nomogram.png`.

Deliverables:
1. Under `VIEW = VASOPRESSOR_CONV` in the open Chromium ICU Portal, export `/home/user/Downloads/icu_round_feed.csv` and copy the Vasopressor Round Seal to the clipboard; inspect **BedsideWave Monitor** on the desktop to identify all beds in red `VTACH!` alarm.
2. Populate `Vaso_Orders` (`A2:E17`) and `Fluid_Envelope` in `ICU_Round_Ledger.xlsx` per `Vaso_Nomogram.png` (`HOLD_VTACH` with `0.0` dose/carrier on `VTACH!` beds; active `Norepi_mcg_min` and `Carrier_mL` on non-alarm beds, preserving `Vaso_Orders!C1`), set `Fluid_Envelope!B2` to the sum of active `Carrier_mL`, set `Fluid_Envelope!B7` to the Vasopressor Round Seal, and size only `Flush_Buffer_A_mL` (`Fluid_Envelope!B4` in `[5, 60]`) so `Total_24h_Fluid_mL` (`Fluid_Envelope!B6`, formula `=SUM(B2:B5)`) lands in `[1900.0, 1908.0]` mL while keeping open LibreOffice windows in sync.
3. Export `/workspace/icu_round/Vasopressor_Orders.pdf` from `ICU_Round_Ledger.xlsx` and write `/workspace/icu_round/VASO_SUMMARY.json` (`vtach_hold_beds`, `total_norepi_mcg_min`, `vaso_carrier_ml`, `vaso_seal`).
