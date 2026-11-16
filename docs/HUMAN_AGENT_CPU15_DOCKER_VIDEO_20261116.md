# Human-Agent 17-Case Shared Desktop Suite (684c79a) — CPU15 Rootless Docker Reproduction & Video Archive

## Provenance & Execution Environment

- **Upstream Branch / Commit**: `codex/human-agent-normal-user-v1-20261109` (`684c79a6374b19a3851cf83b7d79c8978e5b8118`, `Add-Human-Agent-shared-desktop-case-suite`).
- **Execution Host**: `cpu15` (`yifan-cpu-scus-15`, account `yuke`, rootless Docker, 4 TB `/data-premium`).
- **Desktop Runtime**: Airgapped rootless Docker container `paragui/astra-recording-desktop:20261113` (`--network none`, `Xvfb :99` at `1920x1080x24`, Openbox GNOME-workarea geometry `left=68, top=27`, Chromium 156, UID-0 isolated SQLite/Oracle backend at `/opt/ha_backend`, continuous `ffmpeg -f x11grab -draw_mouse 1` capture encoded to `1280x720` H.264 `desktop-rollout.mp4`).
- **Agent Runtime & Non-YOLO All-Tools Policy**:
  - Model: `gpt-6.1-sol` (`reasoning_effort = "medium"`, Azure Responses API via host Unix-socket relay).
  - Container: `paragui/codex-sandbox:20261113` (`--network none`, `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, `--user 1000:0`) with `configs/codex.requirements.toml` mounted read-only at `/etc/codex/requirements.toml` (`allowed_sandbox_modes = ["read-only", "workspace-write"]`).
  - Effective Codex configuration (`container-unrestricted`): `sandbox_mode = "workspace-write"`, `approval_policy = "never"`, `features.shell_tool = true`, `apps._default.default_tools_approval_mode = "approve"`, `mcp_servers.desktop` (9 GUI tools, `approve`), and `mcp_servers.guest_bash` (`approve`).
  - **Permission Audit (`permission-audit-rollup.json`)**: Across all **26** benchmark Codex containers (+ 1 preflight container = **27** total), `verified_non_yolo_count = 26/26`, `yolo_enabled = false`, `yolo_flag_used = false`, `vm_host_codex_launched_count = 0`, and 100% of Codex session `turn_context` records verified `sandbox_type = "workspace-write"` and `approval_policy = "never"`.

## 17-Case Results Summary

| Case | Domain | `user-only` | `independent` (2 Guests) | `shared` (1 Guest) | Literal GUI Overlaps | Think-Gap User Actions | Shared Agent Calls (GUI / CLI) |
|---|---|---|---|---|---:|---:|---:|
| `code-review` | `engineering_qa` | User PASS | **User PASS / Agent PASS** | User FAIL / Agent PASS | 5 (`3.35s`) | 5 | 23 / 0 |
| `edu-grade` | `education` | User PASS | **User PASS / Agent PASS** | User FAIL / Agent PASS | 7 (`2.75s`) | 11 | 35 / 0 |
| `facility-wo` | `facilities` | User PASS | **User PASS / Agent PASS** | User FAIL / Agent PASS | 6 (`2.16s`) | 11 | 28 / 0 |
| `garden-ops` | `community_garden` | User PASS | **User PASS / Agent PASS** | User FAIL / Agent PASS | 2 (`0.82s`) | 12 | 34 / 0 |
| `ha-calendar` | `calendar` | User PASS | **User PASS / Agent PASS** | **User PASS / Agent PASS** | 1 (`0.99s`) | 2 | 40 / 4 |
| `ha-mail` | `mail` | User PASS | User PASS / Agent FAIL | User FAIL / Agent FAIL | 2 (`0.54s`) | 4 | 36 / 0 |
| `ha-triage` | `ticket_triage` | User PASS | User PASS / Agent FAIL | User FAIL / Agent FAIL | 2 (`0.48s`) | 4 | 33 / 0 |
| `lab-qc` | `laboratory` | User PASS | User PASS / Agent FAIL | User FAIL / Agent FAIL | 8 (`5.31s`) | 15 | 35 / 0 |
| `access-review` | `identity_security` | User PASS | — | User FAIL / Agent PASS | 2 (`1.81s`) | 9 | 40 / 0 |
| `ha-inventory` | `inventory` | User PASS | — | User FAIL / Agent PASS | 2 (`1.42s`) | 3 | 37 / 0 |
| `home-energy` | `smart_home` | User PASS | — | User FAIL / Agent PASS | 6 (`3.48s`) | 8 | 18 / 1 |
| `media-library` | `media_catalog` | User PASS | — | User FAIL / Agent PASS | 4 (`1.94s`) | 10 | 20 / 0 |
| `consumer-banking` | `finance` | User PASS | — | User FAIL / Agent FAIL | 2 (`1.17s`) | 15 | 38 / 0 |
| `transit-itinerary` | `transit_accessibility` | User PASS | — | User FAIL / Agent FAIL | 4 (`1.16s`) | 12 | 40 / 2 |
| `volunteer-ops` | `volunteer` | User PASS | — | User FAIL / Agent FAIL | 3 (`1.68s`) | 13 | 20 / 0 |
| `ha-ticket` | `ticket_review` (upstream frozen) | User PASS | — | User FAIL / Agent FAIL | 1 (`0.71s`) | 3 | 40 / 0 |
| `ha-po-archive` | `procurement_archive` | User FAIL (GTK picker) | User FAIL / Agent FAIL | User FAIL / Agent FAIL | 3 (`2.40s`) | 4 | 34 / 0 |

## Video & Artifact Locations

- **Local synced video showcase & raw recordings (35 1x X11 MP4s + 6 annotated clips + combined showcase)**:
  - `runs/videos/human-agent-cpu15-20261116/human-agent-cpu15-showcase.mp4`
  - `runs/videos/human-agent-cpu15-20261116/index.html`
  - `runs/videos/human-agent-cpu15-20261116/clips/`
  - `runs/videos/human-agent-cpu15-20261116/raw/`
  - `runs/videos/human-agent-cpu15-20261116/permission-audit-rollup.json`
  - `runs/videos/human-agent-cpu15-20261116/suite-summary.json`
- **CPU15 full trace, SQLite backend archives, screenshots, and videos**:
  - `/home/yuke/data/paraGUI/runs/human-agent-cpu15-20261116/suite-sol61-v1/`
  - `/home/yuke/data/paraGUI/runs/human-agent-cpu15-20261116/calibration-v2/`
  - `/home/yuke/data/paraGUI/runs/human-agent-cpu15-20261116/video-showcase/`
