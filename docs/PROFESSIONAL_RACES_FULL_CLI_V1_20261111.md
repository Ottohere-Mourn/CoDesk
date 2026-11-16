# Professional-Software Multi-Agent Race Suite (`Full Hybrid GUI+CLI`, `gpt-6.1-sol`)

## Design Principle: Why Ordinary Shared-File Tasks Pass Under Full CLI+GUI, and What Breaks Them

In earlier `Full Hybrid GUI+CLI` experiments (`p1–p3`, `weavebench_writer_conflict`, and `r2/r3` ablations of this suite), coding-capable agents (`gpt-6.1-sol` / `gpt-6-astra`) bypassed GUI focus/selection contention by running fast `<0.3s` Python API scripts (`bpy`, `PyQGIS`, `freecadcmd`, `lxml`) and even re-running their own scripts during final verification if the co-agent had already finished writing earlier (`t_B_commit < t_A_verify`).

Empirical trajectories from `r2`–`r4` establish three necessary conditions for an authentic, unrecoverable concurrent race under **Full Hybrid GUI+CLI** (`ma_id = PASS`, `seq_ba_full_cli = PASS`, `ma_sd_full_cli = FAIL`) without artificial tool bans:

1. **Ticket Role Isolation (`/workspace/role_a` vs `/workspace/role_b`)**: Each agent sees only its own engineering ticket and private input tables, sharing only the canonical native project (`.blend`, `.qgz`+`.gpkg`, `.FCStd`, `.svg`) and live X11 application session.
2. **Non-Trivial Native Compute / Render Critical Sections**: Upstream engineering revisions involve genuine multi-second native computation before commit (Cycles raytraced renders, 6-radius 300-DPI PyQGIS spatial-buffer sensitivity renders, 48-step OpenCASCADE 3D fillet + STL tessellation sweeps, 6-candidate 600-DPI Inkscape contrast renders), creating a wide natural TOCTOU window (`27s–112s` observed tool-call overlap).
3. **Cross-Artifact Physical / Visual Integrity**: Downstream signoff artifacts (raytraced camera frames, SpatiaLite runoff tables & PDF risk atlases, mating STEP solids & bolt-circle gauge pins, 300-DPI prepress plates & ink-coverage metadata) must physically and visually match the final committed native project.

## Live `gpt-6.1-sol` Full Hybrid GUI+CLI Results on `cpu10` (`24/24` Container-Isolated Actors)

- **Permission Audit**: `verified_audit_files = 24`, `vm_host_codex_launched_count = 0`, `yolo_flag_used_count = 0`, `non_docker_marker_count = 0` (`container-unrestricted` inside `--network none --read-only` rootless Docker only).
- **Author Reference Self-Validation (`LLM_rollouts = 0`)**: All 4 tasks pass `pristine = [False, False]`, `a_only = [True, False]`, `b_only = [False, True]`, `seq_ba_joint = True`, `simulated_race_joint = False`.

| Task | Software | `ma_id` (Isolated) | `seq_ba_full_cli` (Sequential Shared) | `ma_sd_full_cli` (Concurrent Shared) | Overlap (s) | FullCLI GUI/CLI Calls | Physical / Visual Race Evidence in `ma_sd_full_cli` |
|---|---|---|---|---|---:|---|---|
| `PR-BLENDER-1` | Blender 3.4.1 | **PASS** (80.8s) | **PASS** (113.1s) | **FAIL** (89.0s) | 39.61 | 0 / 10 | Role A rendered `frame_001.png` (`1.20m` silver) `0.5s` before Role B committed `ECO-B304` (`1.65m` cobalt-blue); fresh Cycles re-render mean RGB diff = **17.41** (`> 8.0` limit) |
| `PR-QGIS-1` | QGIS 3.22.16 | **PASS** (290.4s) | **PASS** (352.5s) | **FAIL** (231.5s) | 112.11 | 0 / 20 | Role A computed 16 `subbasins` runoff & exported `basin_risk_map.pdf` while all culverts were `'OPEN'`; Role B then committed 5 `'BLOCKED'` culverts (`CV-02,05,09,11,14`) & overwrote `watershed_ops.qgz` |
| `PR-FREECAD-1` | FreeCAD 0.20.2 | **PASS** (185.2s) | **PASS** (266.0s) | **FAIL** (242.7s) | 27.53 | 4 / 19 | Role A machined `SpigotCap` to pre-ECO `41.6mm` OD / `30mm` bolt circle; Role B upgraded `BaseHousing` to `48.0mm` bore / `35mm` bolt circle — M6 gauge pins crash into solid cap metal (**716.34 mm³** interference!) |
| `PR-INKSCAPE-1` | Inkscape 1.2.2 | **PASS** (100.2s) | **PASS** (139.6s) | **FAIL** (99.5s) | 27.11 | 0 / 11 | Role A exported `panel_proof_300dpi.png` & `<desc id="qa_ink_ratio">` on orange/1-badge SVG before Role B committed `#0099DD/#00DDFF` + 3 HUD badges; fresh 300-DPI re-render mean RGB diff = **31.40** |

## Code & Artifact Locations

- Task definitions, fixture builders, reference solvers & native graders: `CoDesk/tasks/professional_races_v1/suite.py`
- Containerized Full Hybrid GUI+CLI runner & `0.20s` version watcher: `CoDesk/experiments/professional_races_v1.py`
- Unit tests: `CoDesk/tests/test_professional_races_v1.py`
- Synced comparison results & self-validation: `CoDesk/runs/comparisons/professional-races-v1-sol61-20261111-r4/`
