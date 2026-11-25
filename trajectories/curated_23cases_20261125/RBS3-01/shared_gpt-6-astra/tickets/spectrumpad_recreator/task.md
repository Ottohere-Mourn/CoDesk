# Zero-Source Audio DSP Studio Recreation Work Order — `spectrumpad_recreator`

## Scope & Deliverables
Explore the live **SpectrumPad Studio** desktop application running on the workstation display — including its startup wizard, all 3 preset views (`1`, `2`, `3`) and their 6-band visual EQ bar values (in integer dB), its `F10` Tools popup menu actions, all tabs of its `Preferences` (`Ctrl+P`) dialog, and its `About` (`F1`) dialog — and build a standalone GUI recreation.

Deliverables:
1. **Standalone Recreated GUI Application (`/workspace/recreation/run_app.sh`)**:
   - Launching `bash /workspace/recreation/run_app.sh` (with no arguments) must open a desktop window titled `SpectrumPad Studio` (`>= 760x480`) reproducing the 3 preset views (`1`/`2`/`3`), the 6-band visual EQ canvas, the `F10` Tools menu items, the multi-tab `Preferences` (`Ctrl+P`) dialog, and the `About` (`F1`) dialog.
   - Running `bash /workspace/recreation/run_app.sh --dump-spec-json` must print a single JSON object with exact keys: `"app_title"`, `"build_code"`, `"modes"` (list of 3 strings in `1..3` order), `"mode2_band_gains_db"` (list of 6 integers read from preset `[2]`'s 6 visual EQ bars `B1..B6`), `"menu_actions"` (list of 4 strings from the `F10` popup menu), `"pref_tabs"` (list of 3 tab titles in `Preferences`), `"calibration_offset_db"` (float from `Preferences` tab 2), `"export_format"` (string from tab 3), and `"accent_hex"` (string `#RRGGBB` from tab 3).
2. **Discovered Specification JSON (`/workspace/DISCOVERED_SPEC.json`)**:
   - Save the same JSON object to `/workspace/DISCOVERED_SPEC.json`.
