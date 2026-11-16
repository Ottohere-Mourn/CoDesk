# 10-Task Astra-High Professional & Browser Race Suite (`gpt-6-astra`, `high`, Full Hybrid GUI+CLI)

## Overview & Isolation Audit

- **Evaluated Model**: `gpt-6-astra` with `model_reasoning_effort = "high"`.
- **Action Space**: **Full Hybrid GUI + CLI** (`container-unrestricted`: `approval_policy = "never"`, `sandbox_mode = "workspace-write"`, `shell_tool = true` inside airgapped rootless Docker + `desktop` X11 GUI MCP + unrestricted `guest_bash` workstation CLI, unlocked).
- **Strict Host Safety Audit**: Across all `40` container actor runs (`10 tasks × 2 conditions × 2 roles`), `verified_audit_files = 40`, `vm_host_codex_launched_count = 0`, `yolo_flag_used_count = 0`, `non_docker_marker_count = 0`.
- **Aggregate Outcome**:
  - **Sequential Shared Desktop (`seq_ba_full_cli`)**: **10 / 10 PASS (`100%`)**
  - **Concurrent Shared Desktop (`ma_sd_full_cli`)**: **0 / 10 PASS (`10 / 10 FAIL`, `100%` race reproduction)**

## 10-Task Matrix & Observed Physical / Session Race Evidence

| ID | Software Stack | `seq_ba_full_cli` (Sequential) | `ma_sd_full_cli` (Concurrent) | Overlap (s) | GUI/CLI | Concrete Race Evidence Captured in `ma_sd_full_cli` |
|---|---|---|---|---:|---|---|
| `AR-01` | Blender 3.4.1 (`Cycles` + Rig) | **PASS** (242.2s) | **FAIL** (224.7s) | 30.43 | 0 / 11 | `cam_f020.png` rendered before `52°` emerald-coat wrist pitch ECO committed; frame-20 `GripperJaw` Z & Cycles render mismatch |
| `AR-02` | QGIS 3.22.16 (`PyQGIS` + SpatiaLite + PDF) | **PASS** (476.2s) | **FAIL** (374.7s) | 86.65 | 0 / 15 | 16 `substations` net headroom & PDF exported before 6 ice-loaded feeders (`FDR-01,04,07,10,12,15`) tripped to `0 MW` |
| `AR-03` | FreeCAD 0.20.2 (`OpenCASCADE` BRep + STEP) | **PASS** (131.3s) | **FAIL** (116.8s) | 20.34 | 0 / 8 | `PinionCarrier` machined to `53.5mm` pilot / `40mm` dowel circle while `MainCasing` upgraded to `62mm` bore / `46mm` circle (**1932.51 mm³** pin collision) |
| `AR-04` | GIMP 2.10.34 (Native `.xcf` + Script-Fu) | **PASS** (134.6s) | **FAIL** (92.5s) | 47.20 | 0 / 9 | `press_proof_flat.png` flattened before 8-pass GIMP teal color grade committed to `packaging_master.xcf` (mean RGB diff **12.38**) |
| `AR-05` | MLT `melt` 7.12 + FFmpeg 5.1 + SoX 14.4 | **PASS** (259.1s) | **FAIL** (172.3s) | 48.61 | 0 / 14 | `broadcast_master.mp4` mastered at **72 frames (3.0s)** before director recut extended `commercial_cut.mlt` to **120 frames (5.0s)** |
| `AR-06` | LibreOffice Calc + Writer 7.4 | **PASS** (247.4s) | **FAIL** (135.2s) | 44.36 | 0 / 8 | Board PDF certified `RATIO=3.10 STATUS=COMPLIANT` while IFRS-16 lease debt restatement flipped `.ods` to `RATIO=4.10 STATUS=BREACH` |
| `AR-07` | Chromium 156 + Protected FinOps Portal | **PASS** (191.1s) | **FAIL** (68.0s) | 21.99 | 0 / 7 | `risk_officer` login hijacked uncommitted `treasury_ops` workstation session (`terminal_locked = true`) |
| `AR-08` | Chromium 156 + Inkscape 1.2.2 + DS Portal | **PASS** (143.2s) | **FAIL** (118.1s) | 16.16 | 0 / 9 | `nav_sheet_300dpi.png` & `REL-NAV` staged on `#1E293B` slate palette before `#0EA5E9` cyan theme & alert banner committed |
| `AR-09` | Chromium 156 + Blender 3.4.1 + CPQ Portal | **PASS** (149.5s) | **FAIL** (287.9s) | 94.13 | 0 / 22 | `quote_render.png` rendered on pre-thickened silver `ValveBody` before `INCONEL-625` heavy-wall scaling committed |
| `AR-10` | Git + Graphviz + SQLite3 + Release Gate | **PASS** (125.9s) | **FAIL** (97.4s) | 56.65 | 0 / 16 | Concurrent `git checkout -b` (`feat/telemetry-dag` vs `fix/ledger-rounding`) on shared `.git/HEAD` corrupted branch merge & left dirty tree |

## Code & Artifact Locations

- Suite package: `CoDesk/tasks/astra_races_v2/` (`catalog.py`, `builders.py`, `portals.py`, `graders.py`)
- Containerized `gpt-6-astra` (`high`) runner: `CoDesk/experiments/astra_races_v2.py`
- Unit tests: `CoDesk/tests/test_astra_races_v2.py`
- Synced comparison results & audits: `CoDesk/runs/comparisons/astra-races-v2-high-20261111-r1/`
