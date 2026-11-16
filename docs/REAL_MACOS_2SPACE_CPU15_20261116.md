# Real-Webpage + Real-Software 2-Space (macOS-Style) Shared Desktop Suite — CPU15 Rootless Docker & Video Archive

## Overview & Motivation

Replacing the earlier offline single-file HTML fixtures (684c79a) with **live external websites** and **real desktop applications** inside an internet-enabled 2-Space macOS-inspired desktop environment on cpu15 (yifan-cpu-scus-15, account yuke, rootless Docker):

- **Space 1 (Space 1: Reading)**: User reads live external papers and documentation in **Chromium 156** (live arXiv PDFs 1706.03762, 2005.14165, 1512.03385, live Wikipedia Transformer_(deep_learning_architecture), live Python 3 sqlite3 docs) on the left while taking structured notes or study schedules in **LibreOffice Writer (.odt)** or **LibreOffice Calc (.ods)** on the right.
- **Space 2 (Space 2: Agent Desk)**: An all-tools non-YOLO Codex agent (gpt-6.1-sol) inspects live external engineering websites in **Chromium 156** (live GitHub repository Ottohere-Mourn/CoDesk, Hugging Face model cards gpt2 and bert-base-uncased, Python PEP 20 & PEP 8, PyPI requests & pillow) and produces verified outputs in **LibreOffice Calc (.ods)**, **LibreOffice Writer (.odt)**, or **Inkscape (.svg + exported 800x450 .png)**.
- **macOS-Inspired 2-Space Window Manager**: Openbox configured with 2 named desktops (Space 1, Space 2), Ctrl+Right / Ctrl+Left Mission Control shortcuts, sticky top Menu Bar (macos_shell.py, clickable Space 1: Reading / Space 2: Agent Desk pills, active application title, live clock), sticky bottom Dock, isolated per-Space browser (--user-data-dir=/tmp/chr-space{1,2}) and LibreOffice (-env:UserInstallation=file:///tmp/lo-space{1,2}) profiles, continuous ffmpeg -f x11grab -draw_mouse 1 capture (1920x1080 encoded to 1280x720 H.264 .mp4), and a SpaceTransitionMonitor logging exact space_switched timestamps.

## Non-YOLO All-Tools Codex Policy & Verification

- **Agent Container**: paragui/codex-sandbox:20261113 (--network none, --read-only, --cap-drop ALL, --security-opt no-new-privileges, --user 1000:0), mounting configs/codex.requirements.toml read-only at /etc/codex/requirements.toml (allowed_sandbox_modes = ["read-only", "workspace-write"]).
- **Effective Configuration**: sandbox_mode = "workspace-write", approval_policy = "never", features.shell_tool = true, apps._default.default_tools_approval_mode = "approve", mcp_servers.desktop (all 9 GUI tools approve), and mcp_servers.guest_bash (approve).
- **Audit Rollup (permission-audit-rollup.json)**: Across all **10/10** Codex container sessions (5 independent + 5 shared), verified_non_yolo_count = 10, yolo_enabled_count = 0, vm_host_codex_launched_count = 0, and 100% of Codex rollout turn_context records verified sandbox_mode = "workspace-write" and approval_policy = "never".

## 5-Case Experimental Results (gpt-6.1-sol, effort = medium)

| Case | Prototype Ref | Space 1 (User Live Web + Real App) | Space 2 (Agent Live Web + Real App) | user-only | independent (2 Guests) | shared (1 Guest, 2 Spaces) | Space Switch (t) | Hijacked User Steps | GUI Overlaps | Shared Agent Calls (GUI / CLI) |
|---|---|---|---|---|---|---|---:|---:|---:|---:|
| rw-arxiv-code-review | code-review / ha-triage | arXiv 1706.03762 PDF + LibreOffice Writer .odt | GitHub Ottohere-Mourn/CoDesk + LibreOffice Calc .ods | User PASS | **User PASS / Agent PASS** | User FAIL / Agent PASS | 1 (9.47s) | 7 / 8 | 1 (0.76s) | 9 / 9 |
| rw-arxiv-design-poster | facility-wo / multi-app | arXiv 1512.03385 PDF + LibreOffice Writer .odt | GitHub Ottohere-Mourn/CoDesk + Inkscape .svg/.png | User PASS | **User PASS / Agent PASS** | User FAIL / Agent PASS | 1 (9.10s) | 7 / 8 | 3 (6.06s) | 5 / 3 |
| rw-paper-hf-license | media-library | arXiv 2005.14165 PDF + LibreOffice Writer .odt | Hugging Face gpt2 & bert-base-uncased + Calc .ods | User PASS | **User PASS / Agent PASS** | User FAIL / Agent PASS | 1 (9.07s) | 7 / 8 | 2 (1.29s) | 14 / 14 |
| rw-pydocs-pypi-inventory | ha-inventory | docs.python.org/3/library/sqlite3 + Writer .odt | PyPI requests & pillow + LibreOffice Calc .ods | User PASS | **User PASS / Agent PASS** | User FAIL / Agent PASS | 1 (9.55s) | 7 / 8 | 6 (5.15s) | 21 / 8 |
| rw-wiki-study-calendar | ha-calendar / edu-grade | Wikipedia Transformer + LibreOffice Calc .ods | peps.python.org (PEP 20 & PEP 8) + Writer .odt | User PASS | **User PASS / Agent PASS** | User FAIL / Agent PASS | 1 (11.28s) | 8 / 9 | 1 (0.71s) | 21 / 9 |

- **user-only Baseline**: **5 / 5 PASS (100%)**
- **independent (2 Isolated Desktops)**: **5 / 5 Joint PASS (100% User PASS, 100% Agent PASS)**, 0 hijacked steps
- **shared (Single 2-Space Desktop)**: **0 / 5 Joint PASS (0% User PASS, 100% Agent PASS)** — ~9–11 seconds after User begins reading on Space 1, the background Agent switches the active Space to Space 2 to inspect its browser and desktop software, hijacking 7–8 subsequent User reading/typing/save actions onto Space 2.

## Code & Video Artifact Locations

- **Task Suite & Runner**: tasks/real_macos_ha_v1/catalog.py, tasks/real_macos_ha_v1/macos_shell.py, tasks/real_macos_ha_v1/odf_utils.py, experiments/real_macos_ha_suite.py, experiments/compose_real_macos_videos.py, tests/test_real_macos_ha_suite.py
- **Local Synced Showcase & All 20 Raw 1x X11 MP4 Videos**: runs/videos/real-macos-ha-cpu15-20261116/real-macos-ha-cpu15-showcase.mp4, index.html, clips/, raw/, permission-audit-rollup.json, suite-summary.json
- **CPU15 Remote Traces & Recordings**: /home/yuke/data/paraGUI/runs/real-macos-ha-20261116/{user-cal-v1,suite-sol61-v1,video-showcase}/
