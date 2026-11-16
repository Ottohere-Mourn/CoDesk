# CoDesk 19-Case 4-Arm Benchmark (`gpt-6.1-sol`, Containerized Codex, Native KVM)

## Overview & Provenance

- **Task Source**: Upstream [`Ottohere-Mourn/CoDesk`](https://github.com/Ottohere-Mourn/CoDesk/tree/codex/13-case-handoff-20261104) (`docs/handoff/13-case-handoff/HANDOFF.md`, commit `e5bcbd0362835e30a457795865da949f35906655`), plus pinned sibling branches `codex/case2-v12` (`953d684`), `codex/case3-followup` (`c6bcb56`), and `codex/case4-hardening` (`3462672`).
- **Execution Host**: `cpu10` (`yifan-cpu-wus3-10`), OSWorld Ubuntu 22.04 Guests booted via user-space QEMU 8.2.2 + hardware `/dev/kvm` (`-accel kvm -cpu host`) with read-only base images and per-episode qcow2 overlays.
- **Model**: `gpt-6.1-sol` (`reasoning_effort = "medium"`).
- **Strict Isolation Guarantee**: Zero `codex` processes ever ran on the `cpu10` VM host (`vm_host_codex_launched_count = 0`, `yolo_flag_used_count = 0`, `non_docker_marker_count = 0` across all 188 verified container audit records). Every `codex exec` / `codex exec resume` ran inside an airgapped rootless Docker container (`paragui/professional-rootless:20261103`, `--network none`, `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, `--user 1000:0`) talking to host-side MCP/Responses Unix sockets (`/ipc/mcp.sock`, `/ipc/relay.sock`).

## Four Experimental Arms

| Arm | Guest Topology | Lock | Container Permission Mode | Agent Action Space |
|---|---|---|---|---|
| `ma_id` | Isolated (2 Guests, 1 per actor) | None | `container-read-only-mcp` (`sandbox_mode="read-only"`, `shell_tool=false`) | GUI (`desktop` MCP) + collaboration MCP (+ read-only `guest_cli` where defined by upstream Hybrid-v2) |
| `ma_sd` | Shared (1 Guest, 2 actors) | None | `container-read-only-mcp` (`sandbox_mode="read-only"`, `shell_tool=false`) | Same as `ma_id` on a single shared desktop |
| `ma_sd_lock` | Shared (1 Guest, 2 actors) | Coarse `fcntl.flock` action mutex | `container-read-only-mcp` (`sandbox_mode="read-only"`, `shell_tool=false`) | Same as `ma_sd`, serialized per tool call via host flock |
| `ma_sd_full_cli` | Shared (1 Guest, 2 actors) | **None (Unlocked)** | `container-unrestricted` (`sandbox_mode="workspace-write"`, `approval_policy="never"`, `shell_tool=true`) | **WeaveBench-style Full Hybrid GUI + CLI**: full GUI `desktop` MCP + unrestricted shared Guest VM CLI (`guest_bash` MCP & `/bridge/guest_bash.py`: Bash, Python, LibreOffice UNO, curl, file/process inspection) + collaboration MCP |

## Aggregate Results (19 / 19 Cases Completed)

- **Isolated (`ma_id`) PASS**: **18 / 19** (`94.7%`)
- **Shared GUI / Restricted-CLI (`ma_sd`) PASS**: **5 / 19** (`26.3%`; 2 upstream protocol-gate `environment_or_model_invalid`: `A-01`, `F-01`)
- **Shared + Coarse Action Lock (`ma_sd_lock`) PASS**: **3 / 17** (`17.6%` of evaluated cases; **0 / 11** rescued among `ma_id=PASS, ma_sd=FAIL` cases)
- **Strict `PASS / FAIL / FAIL` Triplet (`ma_id / ma_sd / ma_sd_lock`)**: **11 / 19** (`AUTH-1`, `VIEW-1`, `SITEACT-STATE1`, `PAY-1`, `DATA-REL1`, `AP-1`, `W1`, `C-03`, `U-01`, `EDIT-1`, `FIND-1`)
- **Shared Unlocked Full Hybrid GUI+CLI (`ma_sd_full_cli`) PASS**: **12 / 19** (`63.2%`) — rescuing **6 of 11** strict `PASS / FAIL / FAIL` cases (`PAY-1`, `AP-1`, `W1`, `U-01`, `EDIT-1`, `FIND-1`), **1 of 2** protocol-gated focus cases (`F-01`), and **2 of 2** lock-degraded cases (`CRM-LU1`, `Case-4`), while **7 / 19** semantic/session/clipboard contention cases (`AUTH-1`, `VIEW-1`, `SITEACT-STATE1`, `DATA-REL1`, `A-01`, `Case-2`, `C-03`) still fail without explicit state/session isolation.

## Per-Case 4-Arm Matrix

| Case | Source | `ma_id` | `ma_sd` | `ma_sd_lock` | `ma_sd_full_cli` | FullCLI GUI / CLI Calls | Wall (s) |
|---|---|---|---|---|---|---|---|
| `AUTH-1` | `upstream_complete` | **PASS** | FAIL | FAIL | FAIL | 3 / 0 | 1189.59 |
| `VIEW-1` | `upstream_complete` | **PASS** | FAIL | FAIL | FAIL | 3 / 0 | 1189.91 |
| `CRM-LU1` | `upstream_complete` | **PASS** | **PASS** | FAIL | **PASS** | 13 / 0 | 1799.26 |
| `SITEACT-STATE1` | `upstream_complete` | **PASS** | FAIL | FAIL | FAIL | 14 / 0 | 1752.57 |
| `PAY-1` | `upstream_complete` | **PASS** | FAIL | FAIL | **PASS** | 12 / 3 | 1453.72 |
| `DATA-REL1` | `upstream_complete` | **PASS** | FAIL | FAIL | FAIL | 4 / 5 | 1256.07 |
| `AP-1` | `upstream_complete` | **PASS** | FAIL | FAIL | **PASS** | 11 / 4 | 1813.49 |
| `W1` | `upstream_complete` | **PASS** | FAIL | FAIL | **PASS** | 15 / 6 | 2681.44 |
| `A-01` | `upstream_complete` | **PASS** | `environment_or_model_invalid` | - | FAIL | 3 / 0 | 945.76 |
| `CWD-1` | `codex_transport_migrated` | **PASS** | **PASS** | **PASS** | **PASS** | 12 / 9 | 1785.01 |
| `Case-2` | `upstream_complete` | FAIL | FAIL | FAIL | FAIL | 25 / 2 | 1952.27 |
| `Case-3` | `upstream_complete` | **PASS** | **PASS** | **PASS** | **PASS** | 11 / 0 | 2776.99 |
| `C-03` | `helper_reconstructed` | **PASS** | FAIL | FAIL | FAIL | 1 / 4 | 2266.19 |
| `S-01` | `helper_reconstructed` | **PASS** | **PASS** | **PASS** | **PASS** | 4 / 3 | 2708.79 |
| `U-01` | `helper_reconstructed` | **PASS** | FAIL | FAIL | **PASS** | 12 / 2 | 2321.87 |
| `F-01` | `helper_reconstructed` | **PASS** | `environment_or_model_invalid` | - | **PASS** | 2 / 8 | 3087.28 |
| `EDIT-1` | `helper_reconstructed` | **PASS** | FAIL | FAIL | **PASS** | 6 / 0 | 1870.78 |
| `FIND-1` | `helper_reconstructed` | **PASS** | FAIL | FAIL | **PASS** | 24 / 2 | 2916.93 |
| `Case-4` | `requires_kdenlive_guest` | **PASS** | **PASS** | FAIL | **PASS** | 25 / 0 | 1889.09 |

## Artifact Locations

- Local comparison bundle: `CoDesk/runs/comparisons/codesk-19case-4arm-sol61-20261111-r1/` (`SUMMARY-4ARM.md`, `suite-status-4arm.json`, `permission-audit-rollup.json`, `cases/*/case_summary.json`)
- Remote full trace archive (`cpu10`): `/data/users/yuke/paraGUI/codesk19-sol61-20261111-r1/runs/suite-sol61-20261111-r1/`
