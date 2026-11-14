# V19–V22 GPT-6-Sol 单次三臂实验审计

日期：2026-11-14
Harness：Codex CLI 0.165.0，GUI-only；GPT-6-Sol，高 effort，API base https://api.haogpt.net/v1。每名 Actor 每臂最多 60 次 GUI 调用。密钥不写入仓库。

## 结论

四个 case 的一次结果都满足筛选 tuple：MA-ID 两任务通过；Shared 至少一任务失败；Shared+Lock 至少一任务失败。这是筛选证据，不是重复性结论。每个 arm 顶层结果均为 error=null，失败均由可读取的 Oracle 状态评为 0，而非 SSH/API/Guest 启动失败。

| Case | MA-ID A/B | Shared A/B | Shared+Lock A/B | 单次 tuple |
|---|---:|---:|---:|---|
| V19 | 1/1 | 0/0 | 1/0 | 命中；Shared 同时触及 max-steps 预算，见下 |
| V20 | 1/1 | 0/0 | 1/0 | 命中 |
| V21 | 1/1 | 0/1 | 0/1 | 命中 |
| V22 | 1/1 | 1/0 | 0/1 | 命中 |

## 原始 run 与调用/时间/token 统计

下表按 A/B 顺序列出：Oracle 分数、GUI 调用数、Agent 活动秒数、输入/输出 token。活动秒数是各 Agent 的各自运行时长，并发时不应简单相加作墙钟耗时。

| Case / arm | Run ID | 分数 A/B | 状态 A/B | GUI 调用 A/B | Agent 秒 A/B | Input tokens A/B | Output tokens A/B |
|---|---|---:|---|---:|---:|---:|---:|
| V19 MA-ID | cdesk3-v19-ma-id-20261114T123308Z-2304630 | 1/1 | done/done | 17/30 | 420.1/906.1 | 331,297/818,288 | 741/3,165 |
| V19 Shared | cdesk3-v19-shared-20261114T125146Z-2313319 | 0/0 | max_steps/fail | 60/59 | 1,676.2/1,600.2 | 3,001,911/2,824,925 | 8,000/7,411 |
| V19 Shared+Lock | cdesk3-v19-shared-lock-20261114T132247Z-2326331 | 1/0 | done/done | 44/33 | 716.1/502.1 | 1,599,078/970,056 | 3,576/2,396 |
| V20 MA-ID | cdesk3-v20-ma-id-20261114T133800Z-2332641 | 1/1 | done/done | 13/15 | 170.0/202.0 | 227,161/278,839 | 527/565 |
| V20 Shared | cdesk3-v20-shared-20261114T134458Z-2337289 | 0/0 | fail/done | 30/36 | 710.1/802.1 | 824,885/1,140,894 | 2,475/3,600 |
| V20 Shared+Lock | cdesk3-v20-shared-lock-20261114T140140Z-2345910 | 1/0 | done/done | 37/18 | 710.1/322.0 | 1,163,305/365,191 | 2,892/1,475 |
| V21 MA-ID | cdesk3-v21-ma-id-20261114T141612Z-2352354 | 1/1 | done/done | 15/14 | 258.1/234.1 | 276,285/251,440 | 689/772 |
| V21 Shared | cdesk3-v21-shared-20261114T142420Z-2356956 | 0/1 | fail/done | 34/46 | 656.1/996.1 | 1,040,973/1,784,026 | 4,089/4,289 |
| V21 Shared+Lock | cdesk3-v21-shared-lock-20261114T144359Z-2365445 | 0/1 | fail/done | 35/44 | 906.1/1,242.1 | 1,088,223/1,615,023 | 2,357/2,647 |
| V22 MA-ID | cdesk3-v22-ma-id-20261114T150742Z-2377536 | 1/1 | done/done | 12/15 | 158.0/202.0 | 201,351/276,338 | 485/594 |
| V22 Shared | cdesk3-v22-shared-20261114T151429Z-2381887 | 1/0 | done/fail | 42/29 | 802.1/586.1 | 1,443,997/800,187 | 2,655/3,036 |
| V22 Shared+Lock | cdesk3-v22-shared-lock-20261114T153108Z-2388584 | 0/1 | fail/done | 15/26 | 166.0/372.0 | 277,513/641,415 | 837/1,211 |

## Scripted controls and action-lock telemetry

All four scripted joint Guest positive controls completed with both independent Oracle scores 1.0 and state readable:

- V19 cdesk3-v19-scripted-joint-20261114T122123Z-2297876
- V20 cdesk3-v20-scripted-joint-20261114T122426Z-2299575
- V21 cdesk3-v21-scripted-joint-20261114T122718Z-2301032
- V22 cdesk3-v22-scripted-joint-20261114T123007Z-2302704

V19 Shared is the main qualification caveat: Actor A used all 60 GUI calls and ended max_steps; B used 59. Both exact-state Oracles were readable and scored 0, so this is not infrastructure-invalid, but it couples interference with a hard interaction-budget ceiling. Treat its Shared result as weaker than the other three.

Shared+Lock is a per-GUI-action mutex, not a transaction lock or whole-task reservation. It prevents simultaneous GUI calls but allows the other Actor to switch app panels between calls. Lock telemetry:

| Case | Lock events | Total wait (s) | Mean wait (s) | Max wait (s) | Held total (s) |
|---|---:|---:|---:|---:|---:|
| V19 | 72 | 10.807 | 0.150 | 2.269 | 171.289 |
| V20 | 50 | 4.733 | 0.095 | 2.220 | 115.222 |
| V21 | 71 | 1.902 | 0.027 | 0.988 | 168.056 |
| V22 | 33 | 5.180 | 0.157 | 2.559 | 78.061 |

## 解释范围与限制

- Shared and Shared+Lock tool event streams show both Actors issuing actions in the same Chrome window; logged focus_switch_action=0 and misrouted_focus_before=0 for these runs. No direct OS multi-window focus transition was recorded.
- The tasks use a generated synthetic web application with a shared active-panel/current-record context. They are not real hotel PMS, freight/customs, veterinary EHR, or theatre control systems. The evaluation establishes app-level final field state, not a clinically/operationally consequential real-world outcome.
- The V19–V22 themes vary (hotel turnover/arrival, freight export/load, veterinary sample admin/pickup, theatre turnover/crew call), but the underlying mechanism remains the shared active panel/current record. They complement task-domain coverage; they do not establish four new mechanisms.
- No run was discarded for an undesirable score. Previous invalid transport attempts for V11/V12 are unrelated and remain documented in their prior audit.
- The scripted Guest outputs warn that copying the transient overlay into RAID archive can fail on tmpfs permissions. The controlled app fixture, screenshots, Oracle result, traces, resource logs and model results were complete on RAID; this warning is nonfatal and does not reclassify the run.

## Reproduction and file locations

From the aggregate branch with HealthCare’s existing OSWorld/Guest setup:

```bash
python scripts/run_v456_guest_control.py v19
./scripts/run_new_case_arm.sh v19 ma-id
./scripts/run_new_case_arm.sh v19 shared
./scripts/run_new_case_arm.sh v19 shared-lock
```

Substitute v20, v21, or v22. Fixtures are under /mnt/raid1/mjh/Projects/codesk-next3-20261112/assets/v19..v22; complete run IDs above are under /mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets. Source handoff and values: [case cards](../../docs/FOUR_NEW_DUALAGENT_CASES_V19_V22_20261114_ZH.md). The four scripted controls and 12 model arms are one-shot screening evidence; no repeats were run.
