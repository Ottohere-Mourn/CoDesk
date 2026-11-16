# Ultra-Long-Horizon 4-Task Benchmark (`long_horizon_v1`, `gpt-6.1-sol`, `high`)

## Setup & Non-YOLO Sandbox Audit

- **Execution Host**: `cpu15` (`~/data/paraGUI`), rootless Docker (`paragui/astra-recording-desktop:20261113` + `paragui/codex-sandbox:20261113`).
- **Evaluated Model**: `gpt-6.1-sol` (`model_reasoning_effort = "high"`).
- **Sandbox & Tool Policy**: `sandbox_mode = "workspace-write"`, `approval_policy = "never"`, `shell_tool = true`, `default_tools_approval_mode = "approve"`, read-only `/etc/codex/requirements.toml` (`allowed_sandbox_modes = ["read-only", "workspace-write"]`).
- **Permission Audit (`permission-audit-rollup.json`)**: `verified_audit_files = 16`, `yolo_enabled = false`, `vm_host_codex_launched_count = 0`, `yolo_flag_used_count = 0`.
- **Aggregate Outcome**:
  - **Sequential Shared Desktop (`seq_ba_full_cli`)**: **0 / 4 PASS (`4 / 4 FAIL`)**
  - **Concurrent Shared Desktop (`ma_sd_full_cli`)**: **1 / 4 PASS (`3 / 4 FAIL`)**

## Empirical Results Matrix

| ID | Multi-App Stack | `seq_ba_full_cli` | Seq Gates (A / B) | `ma_sd_full_cli` | Conc Gates (A / B) | DRC Calls (Seq / Conc) | Wall s (Seq / Conc) | Key Physical / Coupled Bottleneck Observed |
|---|---|---|---|---|---|---|---|---|
| `LH-01` | Blender Cycles + Inkscape + Chromium LEED Portal | **FAIL** | `4/6 , 4/6` | **PASS** | `6/6 , 6/6` | `18+17 / 20+24` | `2718.4s / 2472.8s` | Sequential (`45.3m`) Role B left west-glare streak (`p98=0.780 > 0.680`), forcing Role A `contrast_ratio=2.09 > 1.48`; `41.2m` concurrent window allowed 44 total Cycles DRC passes (`p98=0.263`, `contrast=1.182`) |
| `LH-02` | QGIS + SpatiaLite + LibreOffice Calc + Bond Portal | **FAIL** | `4/6 , 6/6` | **FAIL** | `5/6 , 6/6` | `15+163 / 11+377` | `1404.7s / 2243.1s` | Sequential Role B spent `21.50 $M` grey capex minimizing peak flow to `4.75 cms`, leaving zero bond headroom (`total=32.81 $M > 25.80 $M`, `DSCR=1.04 < 1.32`); Concurrent (`37.4m`, 388 DRC calls) Role B overwrote `.qgz` after Role A signoff |
| `LH-03` | FreeCAD + Inkscape + Graphviz + Aerospace PLM Portal | **FAIL** | `4/6 , 6/6` | **FAIL** | `4/6 , 6/6` | `5+3 / 5+2` | `417.2s / 367.6s` | Role B maximized stiffness to `mass_b = 0.680 kg`, making `TopCover >= 82,000 mm³` (`0.231 kg`) exceed total assembly cap (`0.914 kg > 0.855 kg`) in both sequential and concurrent runs |
| `LH-04` | Blender + GIMP + Inkscape + MLT + FFmpeg + SoX + MAM | **FAIL** | `5/6 , 5/5` | **FAIL** | `4/6 , 5/5` | `4+4 / 5+4` | `1246.7s / 2227.8s` | Concurrent (`37.1m`) Role B raised `music_premaster.wav` to `-24.5 LUFS` while Role A mixed unity-gain dialogue, collapsing master `LRA=2.1 LU` (`< 5.2`) and `SNR=2.12 dB` (`< 6.5`); Sequential Role A mismatched canonical `.mlt` SHA signoff |

## Code & Synced Artifacts

- Suite & DRC simulators: `CoDesk/tasks/long_horizon_v1/` (`catalog.py`, `simulators.py`)
- Containerized `gpt-6.1-sol` runner: `CoDesk/experiments/long_horizon_v1.py`
- Unit tests: `CoDesk/tests/test_long_horizon_v1.py`
- Local synced results: `CoDesk/runs/comparisons/long-horizon-v1-sol61-20261113-r1/`
- Remote full archive & X11 recordings (`cpu15`): `~/data/paraGUI/runs/long-horizon-v1-sol61-20261113/r1/`
