# 4-Agent Concurrent Hybrid GUI+CLI Benchmark (`quad_hybrid_v1`, `gpt-6.1-sol`, `high`)

## Design: Natural GUI Requirement + Full Unrestricted CLI (Zero Artificial CLI Bans)

- **4 Tasks × 4 Concurrent Agents (`B, C, D, A`)** on one shared `1280x720` X11 desktop (`DISPLAY=:99`) and shared `/workspace`:
  - `QH-01`: **Product Launch Studio** (`Blender 3.4 + GIMP 2.10 + Inkscape 1.2 + LibreOffice Calc + Chromium Launch Studio`)
  - `QH-02`: **Smart-Grid Emergency Dispatch** (`QGIS 3.22 + SpatiaLite + Graphviz + LibreOffice Calc/Writer + Chromium Grid Console`)
  - `QH-03`: **Robotics Workcell PLM** (`FreeCAD 0.20 + Blender 3.4 + Inkscape 1.2 + Chromium PLM Blueprint Console`)
  - `QH-04`: **Master Control Room (MCR)** (`MLT melt + FFmpeg + SoX + GIMP 2.10 + LibreOffice Calc + Chromium MCR Switcher`)
- **Why GUI and CLI are both genuinely used**:
  - **GUI (`desktop`: `screenshot`, `click`, `type_text`, `key`, `wait`)**: Module specifications are rendered graphically onto HTML5 `<canvas>` cards inside an already-authenticated Chromium window (`UID 1001`, isolated `HttpOnly` session cookie on `DISPLAY=:99`), and module staging/commits happen through the live Studio UI.
  - **CLI (`guest_bash`)**: Completely unrestricted (`UID 1000` on `/workspace`) for Blender Cycles, PyQGIS, FreeCAD OpenCASCADE, GIMP Script-Fu, Inkscape, Graphviz, LibreOffice, and MLT/FFmpeg/SoX.
- **Non-YOLO Sandbox Audit**: Across all **96 containerized agent rollouts** (`r1`, `r2`, `r3`: `32` verified audit records per round), `sandbox_mode = "workspace-write"`, `approval_policy = "never"`, `yolo_enabled = false`, `vm_host_codex_launched_count = 0`.

## Live `gpt-6.1-sol` (`high`) Results on `cpu15`

### Round `r3` (Module-Scoped Single 8s Preview Buffer, Clean `/workspace`)

| ID | `seq_4role_full_cli` (`B->C->D->A`) | Seq GUI (Act+Obs) / CLI | `quad_sd_full_cli` (4 Concurrent) | Quad GUI (Act+Obs) / CLI | Tab Switches (Seq / Quad) | Wall s (Seq / Quad) | Speedup |
|---|---|---|---|---|---|---|---:|
| `QH-01` | **PASS (4/4)** | `47+16 / 26` | **FAIL (0/4, buffer tainted: 3 preview aborts)** | `70+40 / 74` | `4 / 15` | `526.9s / 458.6s` | FAIL |
| `QH-02` | **PASS (4/4)** | `48+17 / 32` | **PASS (4/4)** (`r1`: **FAIL 3/4**) | `81+42 / 91` | `5 / 5` | `626.8s / 442.8s` | `1.42x` |
| `QH-03` | **PASS (4/4)** | `44+13 / 21` | **PASS (4/4, 1 preview abort)** | `67+49 / 92` | `4 / 8` | `432.7s / 418.5s` | `1.03x` |
| `QH-04` | **PASS (4/4)** | `42+13 / 22` | **PASS (4/4)** | `71+38 / 87` | `5 / 5` | `469.8s / 420.8s` | `1.12x` |

### Rounds `r1` (Shared 4-Card Spec Canvas) & `r2` (Role-Scoped Tabs + Shared Scratch)

- **`r1`**: `seq_4role_full_cli` **4/4 PASS**; `quad_sd_full_cli` **3/4 PASS (`QH-02` FAIL 3/4)**, with massive GUI contention (`QH-01`: `174` GUI calls vs `52` sequential, `25` tab switches vs `7`, **negative speedup `580.0s > 501.1s`**; `QH-04`: **negative speedup `521.2s > 451.8s`**).
- **`r2`**: `seq_4role_full_cli` **4/4 PASS**; `quad_sd_full_cli` **4/4 PASS**, where trajectories show the 4 `gpt-6.1-sol` agents detecting X11 tab theft (`"B just stole tab..."`) and **spontaneously inventing ad-hoc filesystem lockfiles (`/tmp/GUI_OWNER`, `ROLE_*_DONE`)** to self-serialize GUI access — rescuing accuracy at the cost of **`2.5x–3.3x` GUI calls (`112–159` vs `47–49`)**, **`2.5x–4.1x` CLI calls**, and negative speedup on `QH-01` (`521.9s > 427.4s`).

## Code & Artifact Locations

- Task package: `CoDesk/tasks/quad_hybrid_v1/` (`catalog.py`, `portals.py`, `suite.py`)
- 4-Agent runner: `CoDesk/experiments/quad_hybrid_v1.py`
- Unit tests: `CoDesk/tests/test_quad_hybrid_v1.py`
- Local synced results (`r1`, `r2`, `r3`): `CoDesk/runs/comparisons/quad-hybrid-v1-sol61-20261114/`
- Remote archive & `desktop-rollout.mp4` X11 videos (`cpu15`): `~/data/paraGUI/runs/quad-hybrid-v1-sol61-20261114/`
