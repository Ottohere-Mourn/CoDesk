# CONC Batch 1 — Live Status

Last updated: 2026-11-25 (local). This status separates observed facts from assumptions. No credential values are stored here.

## Approved run parameters

- One shared A+B Guest run per case; no A-only/B-only baseline runs.
- `gpt-6-sol` for both roles; no step cap (`--max-steps 0`) and 7,200 seconds per role.
- Queue maximum is eight, but actual launch concurrency is controlled by read-only preflight.
- English runtime UI, task instructions, generated assets, and presentation text; no online package installation.
- Full screenshots and run logs are retained under the HealthCare RAID run root. API image input is hard capped at four globally; verified `sub2api-hk` native-computer calls are currently limited to one frame per request. Historical frames remain on RAID; no tool-call pairing is pruned.
- API credentials remain in HealthCare's existing private process-injection path; no key value is recorded in source, manifest, task prompt, log, or this status.

## Specifications

- The approved location was `C:\Users\33114\Downloads`. A recursive read-only search found no `CONC-*.md` files at the time checked.
- Working copies used for this batch are `case_work/20261125-conc-batch1/CONC-01..CONC-08/SPEC.zh.md`. Their identity with the requested Downloads originals remains unverified.

## Case progress

| Case | Build/checks | Shared Guest state |
|---|---|---|
| CONC-01 | Implemented; deterministic fixtures and audit previously passed. | `CONC-01-shared-r2-20261125` running; latest file listing showed over 500 Actor A and over 480 Actor B step screenshots. |
| CONC-02 | Implemented; deterministic fixtures and audit previously passed. | r6 ended at zero agent steps after the endpoint rejected multiple images. r8 also ended at zero steps because the setup script copied from `/home/user/.cache/paragui/conc02/guest/...` while staged inputs were under `/home/user/.cache/paragui/conc02/CONC-02/guest/...`. The root mismatch is now corrected and r9 is queued; the retry will confirm whether any remaining infrastructure issue exists. |
| CONC-03 | Implemented; deterministic fixtures and audit previously passed. | `CONC-03-shared-r2-20261125` running; latest listing showed over 570 Actor A and over 410 Actor B step screenshots. |
| CONC-04 | Implemented; 18/18 suite, audit 9 files/0 FAIL/WARN, deterministic fixture gates pass. | `CONC-04-shared-r1-20261125` running; latest listing showed over 210 Actor A and over 210 Actor B step screenshots. |
| CONC-05 | Implemented; dedicated unit, audit, and self-validation previously passed deterministic gates. | `CONC-05-shared-r1-20261125` running; latest listing showed over 280 Actor A and over 270 Actor B step screenshots. |
| CONC-06 | Implemented. Targeted tests 3/3; `audit_case_module.py` 9 files/0 FAIL/WARN; deterministic fixture checks Gates 1–4 and fixture feasibility pass. Real-Guest Gate 5 remains pending. | `CONC-06-shared-r1-20261125` appended to queue and is pending behind four running Guests. |
| CONC-07 | Implemented; targeted tests 3/3, audit 9 files/0 FAIL/WARN, fixture checks pass. `self_validate.py` reports abstract Gate 1-4 + fixture feasibility pass; real Guest Gate 5 remains pending. | `CONC-07-shared-r1-20261125` appended to queue; awaiting preflight capacity. |
| CONC-08 | Implemented; targeted tests 5/5, audit 10 files/0 FAIL/WARN, fixture Gates 1-4 + fixture feasibility pass. Workbook XLSX authored with Artifact Tool and rendered previews inspected. `self_validate.py` leaves real Guest Gate 5 pending. | `CONC-08-shared-r1-20261125` appended and picked up as pending by the live queue. The pre-agent Calc probe runs during setup; if unavailable, setup must record `SKIPPED_NO_CALC` and abort before actor calls. |

## HealthCare queue and resources

- Queue worker directory: `/mnt/raid1/mjh/codesk-runs/conc-batch1-20261125/agent-queue-v5/`.
- Archive root: `/mnt/raid1/mjh/codesk-runs/conc-batch1-20261125/agent-queue-v5/runs/`.
- Latest preflight observed MemAvailable about 158 GiB, swap 2/2 GiB used with no active swap I/O detected, root free about 30.3 GiB, RAID free about 603.9 GiB, `/dev/shm` free about 99.7 GiB, Docker available, and `/dev/kvm` present. The queue currently permits four concurrent Guests, so C06 remains queued; no queue/Guest process was stopped.
- CONC-01/03/04/05 are the four active jobs; CONC-06, CONC-07, corrected retry `CONC-02-shared-r9-20261125`, and `CONC-08-shared-r1-20261125` are pending. Latest queue state (2026-11-24 22:23 UTC) shows capacity 4. Preflight repeats before each launch.
- All current manifest jobs use `https://sub2api-hk.ziplab.co/v1`; the active Guest agent configurations were read with auth fields excluded and show model `gpt-6-sol`. No credential value is in the job manifest.
- Screenshots and failed-run artifacts are retained. No run data was deleted.

## Validation interpretation

`self_validate.py` for CONC-06 reports pristine failure, both abstract actor orders, and naive-race corruption as PASS, plus fixture feasibility PASS. It reports careful-concurrency / real-tool timing as pending because the shared Guest episode has not yet completed. The user's throughput instruction permits queueing after deterministic tests, audit, and self-validation without waiting for a separate timing document.


## Agent-route diagnosis (separate read-only audit)

A delegated read-only audit of an earlier real-Guest agent startup found one run whose Codex subprocess loaded a `CODEX_HOME/config.toml` pointing to `https://api.openai.com/v1` rather than the intended proxy endpoint. The audit did not find proof of an HTTP request or a 401/403 response, so the override mechanism/root cause remains unresolved. A second audit found a different historical real-agent run that did execute GUI actions and later failed at the provider's 50-image request cap; it is not evidence that the current four batch runs lack agent connectivity. Current batch screenshots prove GUI actions are being emitted, but final API/agent completion results remain pending. No credentials were read or exposed by the audit.

- CONC-02 retry r9 uses updated cache root `/home/user/.cache/paragui/conc02/CONC-02`; its new staging file was verified on RAID.
- Four current runs have emitted large complete per-agent screenshot sequences, confirming both actors are interacting. Latest read-only counts (2026-11-24 22:41 UTC): C01 640/617, C03 835/606, C04 328/328, C05 466/460 (A/B). Combined screenshot storage observed was about 1.9 GiB at that snapshot; RAID remains ample. They remain active; no Guest/process was stopped. A read-only inventory finds PPTX artifact candidates for C03, but no final score/result is available yet.
- The queue has now parsed and accepted all eight distinct current batch entries (including C08). At the latest snapshot it has four active Guests and four pending jobs: C06, C07, C02-r9, C08. The queue manifest JSONL was validated after appending C08; no credential data is in the manifest.
- Read-only live-agent diagnosis (2026-11-24 22:59 UTC; no run stopped): C01 and C03 are still active, with screenshot-step files C01 A/B 715/697 and C03 A/B 985/730; neither has a final `result.json`. In the latest ten combined response blocks from C01 `driver.log`, all ten raw tool actions were `screenshot`; C03's latest ten were nine `screenshot` and one `keypress`+`type`. All sampled requests returned HTTP 200 and no provider error was visible. These logs are merged and have no reliable per-actor tags before result finalization, so this is not an exact A-vs-B latest-10 transcript. C01 per-agent caches contain no deliverable files. C03's cached `Safety_Brief.pptx` is byte-identical to the staged starter template (same SHA-256), so it is not agent progress; neither case has a verified new artifact yet.
- Read-only request-path audit: active `agents.json` points at the staged `paragui_batch.stateless_cua:make` policy (not `oscombo.policies.stateless_openai_cua`). For sub2api it selects one image per request, so no old images are sent. Image limiting does not delete text, but the policy intentionally clears `previous_response_id`/pending turn items at each outer step and rebuilds context from the task prompt plus up to six concrete own-action summaries and three response notes. Screenshot/observe actions are filtered from concrete-action history and returned actions; there is no corresponding "never request screenshot" prompt in that staged policy. Thus the recent screenshot-only calls are consistent with a no-op observe loop / weak carryover, not evidence that the image-window code deletes text. Per-response log label `GPT-5.4` is hard-coded in the client; active per-agent config says `gpt-6-sol`, so that label alone does not establish the actual selected model.
- The route diagnosis subagent found a historical run configured for `api.openai.com/v1` with unresolved provider override, but did not observe an HTTP 401/403. A separate historical run reached the provider and hit the old 50-image cap after many GUI actions. Current active batch shows sustained agent steps using the sub2api endpoint; final completion records remain pending.

## 2026-11-25 — stop request and formal Codex harness gate (supersedes the live-state entries above)

- **Old shared-run stop:** The four earlier active Guests were stopped to release VM resources; current `docker ps` is empty. The stopped Docker records were retained (no container/data cleanup). The queue-v6 launcher and its runner were stopped. A later process sweep found four older detached idle queue workers (`run_batch_queue_v2.py` through `run_batch_queue_v5.py`, PIDs 2370102, 2392147, 2402410, 2425107); all four received SIGTERM and were confirmed absent on recheck. There are now no matching batch queue, `oscombo run`, image-relay, or CONC-01 pilot processes. The old Guest stop was performed at the Docker runtime because the queue process had inherited SIGINT as ignored; **do not claim `env.close()` ran for those four Guests**. Their runtime containers are stopped and resources released.
- **Formal harness research:** A previously successful `oscombo` Codex-harness path exists in `/home/mjh/Projects/CoDesk-case2-healthcare` (branch `codex/gui-cli-mcp-v2`, existing dirty worktree left untouched). Its `CodexHarness` uses the Codex CLI with persistent native multi-turn context, desktop MCP, and a read-only allowlisted Guest CLI MCP. A historical HealthCare hybrid-v2 smoke record reports valid GUI + Guest CLI operation with GPT-6-Sol. The earlier v6 implementation was instead hard-wired to `paragui_batch.stateless_cua:make`; that was a runner selection mistake, not evidence that the Codex harness could not run.
- **CONC-01 shared 15-step pilot:** Started one Guest run using Codex CLI 0.155.0, model `gpt-6-sol`, the Codex GUI + Guest CLI harness, and per-actor image relays that promote only the latest tool screenshot into API context while retaining screenshot artifacts on RAID. The run root is `/mnt/raid1/mjh/codesk-runs/conc-batch1-20261125/agent-queue-v5/runs/CONC-01-codex-shared-pilot15-20261124T232457Z/`.
- **Gate outcome: FAIL; do not restart the eight-case queue.** Both `agentA/stderr.log` and `agentB/stderr.log` show Codex session initialization failed before any Actor step: required MCP servers `desktop` and `guest_cli` each closed during handshake (`initialize response: connection closed`; `thread/start` failed, code `-32603`). Both actor stdout files are empty; there are no action logs or relay request events, so neither actor reached a GUI click/input or Guest CLI command and no model API request is evidenced. The 15-step gate was not reached and fails. A transient Chrome websocket `socket hang up` during setup recovered and both service pages opened; the runner later logged a file-getter 404 while interrupted during teardown/evaluation, but this does not replace the earlier MCP-init blocker. The runner and relays are absent and there are zero active Docker Guests after the pilot stop; no stateless fallback was used. Pilot screenshots/logs remain archived.
- **Next action (plan only):** Diagnose why the two MCP servers fail to initialize in this `oscombo run` launch (without starting the eight-case queue); once the formal harness can pass the same bounded two-actor gate, rerun the pilot and only then consider the approved shared queue. The formal harness exposes a read-only Guest CLI allowlist (e.g. `pwd`, `ls`, `cat`, `stat`, `grep`, `head`, `tail`), so it is not an unrestricted Guest shell; keep that limitation explicit.

## 2026-11-25 — MCP handshake root-cause check and bounded retry

### 1) Historical-vs-pilot comparison (read-only)

- Historical successful artifacts: `/mnt/raid1/codesk-hybrid-v2-smoke-20261103T194500Z/smoke_result.json` and `/home/mjh/Projects/CoDesk-case2-healthcare/runs/hybrid_v2_ttr_pilot_20261103/triplet_summary.md`. The smoke records Codex CLI 0.155.0, MCP SDK 1.12.4, `gpt-6-sol`, both desktop and Guest CLI permissions, and valid A/B runs. The TTR summary records the same Codex CLI/model and three MCP permissions.
- The historical generated Actor config uses MCP executable `/home/mjh/.local/share/codesk-hybrid-v2/mcp-venv/bin/python`, `-m oscombo.desktop_tools --mcp` and `-m oscombo.guest_cli_tools`, and per-server `PYTHONPATH` containing both the CoDesk worktree and `/home/mjh/.local/share/codesk-hybrid-v2/mcp-site-1.12.4` (the TTR config's actual order is worktree then MCP site). Its `[mcp_servers.desktop]` and `[mcp_servers.guest_cli]` are enabled and required; startup timeouts are 60s and 30s. Runtime env includes Guest URL, action log, max-step limit, actor/episode/condition metadata, and `PYTHONPATH`; secret-valued fields are deliberately not reproduced here.
- The failed pilot had the same Codex CLI, MCP Python executable, server module commands/args, required-server setting, and base Codex model/provider structure. Its parent runner `PYTHONPATH` had the worktree, compatibility overlay, staged runner source, runner overlay, and OSWorld source—but **did not include `mcp-site-1.12.4` in the per-MCP-server environment**. The separate MCP SDK is installed under that site directory, not in `mcp-venv`; therefore both server modules could import `oscombo` but not `mcp`. Pilot MCP config omitted `collaboration` because none was configured; that did not account for the desktop/Guest CLI failures.
- A first corrective attempt added `mcp-site-1.12.4` to the *whole runner* `PYTHONPATH`. That was not safe: it shadowed OSWorld's Pillow with the MCP-site `PIL` package and the run ended before agent startup with `ImportError: cannot import name '_imaging' from PIL`. I removed that global addition and instead scoped the MCP site path to each Actor's MCP-server `PYTHONPATH`, matching the historical profile. A read-only preflight with the normal runner path then imported `PIL.Image` and `oscombo` successfully.

### 2) Exact manual MCP stderr and corrected handshake probe

With the first pilot's generated commands and environment, I manually started each stdio MCP server and captured its full stderr. Both fail identically at the import boundary:

```text
desktop:
Traceback (most recent call last):
  File "/usr/lib/python3.10/runpy.py", line 196, in _run_module_as_main
    return _run_code(code, main_globals, None,
  File "/usr/lib/python3.10/runpy.py", line 86, in _run_code
    exec(code, run_globals)
  File "/home/mjh/Projects/CoDesk-case2-healthcare/oscombo/desktop_tools.py", line 598, in <module>
    main(sys.argv[1:])
  File "/home/mjh/Projects/CoDesk-case2-healthcare/oscombo/desktop_tools.py", line 588, in main
    mcp_main()
  File "/home/mjh/Projects/CoDesk-case2-healthcare/oscombo/desktop_tools.py", line 539, in mcp_main
    from mcp.server.fastmcp import FastMCP, Image
ModuleNotFoundError: No module named 'mcp'

guest_cli:
Traceback (most recent call last):
  File "/usr/lib/python3.10/runpy.py", line 196, in _run_module_as_main
    return _run_code(code, main_globals, None,
  File "/usr/lib/python3.10/runpy.py", line 86, in _run_code
    exec(code, run_globals)
  File "/home/mjh/Projects/CoDesk-case2-healthcare/oscombo/guest_cli_tools.py", line 221, in <module>
    mcp_main()
  File "/home/mjh/Projects/CoDesk-case2-healthcare/oscombo/guest_cli_tools.py", line 204, in mcp_main
    from mcp.server.fastmcp import FastMCP
ModuleNotFoundError: No module named 'mcp'
```

After adding only the MCP-site path to MCP-server env, each server returned a valid `initialize` response and `tools/list` response (desktop: 9 tools; Guest CLI: 1 tool). Corrected-probe stderr contained only the SDK's `IncompleteFieldDefinitionWarning` for `lifespan` and normal `Processing request of type ListToolsRequest`; no traceback or handshake error.

### 3) Corrected CONC-01 pilot result and stop decision

- Retried one shared Guest pilot at `/mnt/raid1/mjh/codesk-runs/conc-batch1-20261125/agent-queue-v5/runs/CONC-01-codex-shared-pilot15-20261124T235038Z/`, with MCP-site `PYTHONPATH` scoped per MCP server. The run successfully set up both service pages; the Codex relay request advertised both `mcp__desktop` and `mcp__guest_cli`, consistent with successful Codex-side server initialization.
- **The 15-step gate still fails due to provider/API 503, before any Actor action.** Both actors received the upstream response `503 Service Unavailable: The group daily usage authorization service is temporarily unavailable.` Codex emitted three reconnect retries then `turn.failed`; each actor's relay recorded 16 upstream-503 events, zero image parts, and neither actor produced an action log. Thus there was no GUI/CLI action and the pilot did not reach the 15-step gate. This is a provider authorization-service availability response, not an MCP import error; no credential contents were read or logged in this investigation.
- The evaluator subsequently retried fetching nonexistent outputs (HTTP 404) because the Actors had not run. I interrupted the runner during that evaluation retry; the launcher/runner/relays are now absent and `docker ps` is empty. **Do not restart the eight-case queue**: the user-specified pilot API/no-error condition did not pass. No stateless fallback was used.
- **Next action (plan only):** wait on the 503 provider-availability blocker. After the endpoint is available, rerun the same bounded 15-step pilot using the now-correct per-MCP `PYTHONPATH`; proceed to the eight-case queue only if the API responds successfully and both Actors produce real GUI/CLI actions within their first 10 steps.

### Startup command and environment record

- The exact historical parent shell command was not persisted in the inspected TTR/smoke summary artifacts; I did not invent one. The historical Codex child argv is confirmed from `oscombo/harness/external.py`: `[codex-0.155.0, "exec", "--json", "--skip-git-repo-check", "-C", <Actor work dir>, <task prompt>]`, with `CODEX_HOME=<Actor runtime>/codex_home`; the generated TTR and smoke configs confirm the executable/MCP commands above.
- The current pilot's actual runner argv was `osworld-venv/bin/python -m oscombo run --mode parallel --tasks <CONC-01 A task> <CONC-01 B task> --out <pilot run root> --agents <pilot agents.json> --image /dev/shm/codesk-next3/osworld-v2-ubuntu-x86.qcow2 --max-steps 15 --setup-settle 30`. Codex child argv is generated by the same `CodexHarness.command` implementation. Runner Python is `/home/mjh/.cache/codesk-food-recall-setup-20261124/osworld-venv/bin/python`; MCP Python is `/home/mjh/.local/share/codesk-hybrid-v2/mcp-venv/bin/python`; Node runtime directory is `/home/mjh/.local/share/codesk-case3-tools`.
- Historical Actor MCP env has `PYTHONPATH` containing both `<CoDesk worktree>` and `<CODEX_HYBRID_HOME>/mcp-site-1.12.4`; pilot initially passed only `<worktree>:<worktree>:<python-compat-v1>:<staged runner source>:<runner overlay>:<OSWorld source>`. After the root-cause finding, the pilot script now sets `PYTHONPATH=<mcp-site-1.12.4>:<runner PYTHONPATH>` only in `options.mcp_env`, not in the runner's process environment. This avoids the observed Pillow module shadowing while making `mcp.server.fastmcp` importable.

## 2026-11-25 — requested pilot rerun after API recovery

- Started `CONC-01-codex-shared-pilot15-20261125T001243Z` using the formal persistent Codex CLI harness (`gpt-6-sol`), per-Actor loopback Responses relays to HaoGPT, and MCP-server-scoped `PYTHONPATH` beginning with `/home/mjh/.local/share/codesk-hybrid-v2/mcp-site-1.12.4`. The relay was configured to retain text history and forward only the latest desktop tool screenshot while leaving screenshots/logs on RAID. The provider key was read from the existing private HealthCare injection file into process memory only.
- **Gate FAIL before actor startup: Guest task setup repeatedly reported `Custom task setup failed: Setup Download - Local source not found: /home/mjh/.cache/oscombo/paragui/assets/CONC-01/service.py` (first setup retry 1/5).** The runner result has no Actor records; `agentA/actions.jsonl` and `agentB/actions.jsonl` were never created; both relay event logs contain no requests. Thus this run does not verify MCP handshakes, HTTP 200, or any A/B GUI/CLI actions. No 503 was observed because the agents never reached the API.
- Per the stop condition, sent SIGINT to the matching `oscombo run` process to allow graceful environment teardown. The pilot runner exited; a subsequent read-only check found `docker ps` empty and no matching pilot/relay processes. The run's logs/result remain archived at `/mnt/raid1/mjh/codesk-runs/conc-batch1-20261125/agent-queue-v5/runs/CONC-01-codex-shared-pilot15-20261125T001243Z/`.
- **The eight-case queue was not started; no stateless fallback was used.** Next action is to fix the task setup source-path mapping and rerun only the bounded 15-step gate. Do not start the full queue unless that gate passes.

## 2026-11-25 — corrected staging mapping and pilot rerun in progress

- Rechecked all eight case-specific `task-assets/<CONC-xx>` directories with recursive file counts before starting the Guest. All eight staging roots exist (C01: 2 files, C02: 11, C03: 9, C04: 5, C05: 6, C06: 16, C07: 34, C08: 24); the full paths and sample filenames are archived in the pilot's `asset_preflight.json`.
- The 07:51 successful pilot log confirms the runner expected `PARAGUI_TASK_ASSETS=/mnt/raid1/mjh/codesk-runs/conc-batch1-20261125/staging/CONC-01-shared-r2/task-assets`. The corrected pilot explicitly supplies that mapping to the runner process; per-Actor MCP `PYTHONPATH` continues to begin with `mcp-site-1.12.4` and the Codex CLI model is `gpt-6-sol`.
- Corrected rerun `CONC-01-codex-shared-pilot15-20261125T004103Z` is active on HealthCare. It uses the formal persistent Codex harness with desktop + read-only Guest CLI MCP and the image-limiting relay. The 15-step gate has not yet been adjudicated; no eight-case queue has been started.
- The corrected runner log now confirms both setup tasks copied `service.py` from the staging root (not the default cache), and both service health checks passed. Both actor relays have returned HTTP 200 for `gpt-6-sol`; their advertised tool set includes both `mcp__desktop` and `mcp__guest_cli`. Early action logs contain actual GUI clicks/keys for both actors (A: two clicks; B: click + key presses), so startup is no longer screenshot-only. The 15-step gate is still running to collect and verify the bounded pilot result.
- At preflight: MemAvailable was previously around 177 GiB, root filesystem had ~30.2 GiB free, RAID ~602 GiB free, `/dev/shm` ~99.8 GiB free; Docker/KVM are available. One pilot Guest was launched. No pre-existing `oscombo run` or image relay was detected. No prior data was removed.

## 2026-11-25 — pilot gate and formal Codex queue

- Corrected pilot `CONC-01-codex-shared-pilot15-20261125T004103Z` verified that both A/B setup copies read `service.py` from the intended staged task-assets root. Codex advertised both required MCP servers; Actor A made 13 tool calls including multiple executed GUI clicks/keys, and Actor B made 10 including executed GUI click/key/type actions. All 25 relay requests returned HTTP 200 for `gpt-6-sol`; each request carried at most one image. No API error or unresolved MCP/setup startup error occurred.
- **Harness/action self-check: PASS.** The task itself did not produce a deliverable in this bounded pilot: both actors called `declare_infeasible` for different task-level reasons (A: believed it lacked a way to save/verify the requested browser artifacts; B: inferred the display was too small from the model-scaled screenshot). The Guest screenshot metadata records 1920×1080 physical and 1280×720 model-scaled dimensions. Evaluation then retried HTTP 404 fetches for outputs that were never created; after both actor turns completed, I sent SIGINT to end the repeated missing-output evaluation and allow environment teardown. Runner exit was `-2`; `docker ps` is empty and the run-owned relays are stopped. This is a task-outcome warning, not an API/MCP gate failure.
- Per the approved auto-decision rule, the all-eight **shared-only** queue is now running on the formal Codex harness (no stateless driver). It is an asynchronous four-Guest queue with per-launch resource preflight. At the latest HealthCare update, CONC-01..04 were running and CONC-05..08 queued. Model `gpt-6-sol`; both actors use desktop + read-only Guest CLI MCP; per-case `PARAGUI_TASK_ASSETS` points to that case’s verified staged root. Tool-call budget is set to 2,147,483,647 to avoid a practical step cutoff; the separate wall-time safety timeout is 7,200 seconds per actor/run.
- Live queue status and logs are on HealthCare RAID: `/mnt/raid1/mjh/codesk-runs/conc-batch1-20261125/agent-queue-codex-v1/STATUS.md` and `/mnt/raid1/mjh/codesk-runs/conc-batch1-20261125/agent-queue-codex-v1/runs/`. The relay retains only the latest tool screenshot per API request while keeping full text/tool history and all screenshot artifacts on disk.
- Queue snapshot 2026-11-25 00:54 UTC: C01 A/B 4/4 actions (both relays HTTP 200), C03 7/7 (both 200), C04 3/5 (both 200), C02 still in setup/initialization (A/B actions 0/0; B relay has returned 200). C05–C08 remain queued behind the four active Guests. No API error is recorded in the live relay status so far.
- C08 Calc availability probe (read-only, same Ubuntu Guest image, no package changes): Guest `/execute` returned HTTP 200; `/usr/bin/libreoffice` and `/usr/lib/libreoffice/program/scalc` exist, and `dpkg-query` reports `libreoffice-calc` installed. C08 will not be skipped for missing Calc.
- A live-process audit of the four current runner environments confirms each `PARAGUI_TASK_ASSETS` points to its own staged root (C01, C02-r9, C03, C04; all directories exist) and each A/B config uses `harness=codex`, `model=gpt-6-sol`, `guest_cli` enabled, with MCP `PYTHONPATH` prefixed by `mcp-site-1.12.4`. This directly verifies the corrected mapping is active, not just present in a plan file.
- Queue snapshot 2026-11-25 00:56 UTC: all four active cases have both actor relays returning HTTP 200. Action counts were C01 21/21, C02 7/13, C03 31/22, C04 18/20. Recent action samples show substantial click/type/key activity for C03/C04 and Guest CLI calls for C02; no screenshot-only loop was observed. Both C01 actors again called `declare_infeasible` during the full shared run, and C02 Actor A did so early; queue continues for the remaining actors/cases while the 404 evaluator monitor protects Guest slots.
- Queue snapshot 2026-11-25 00:57 UTC: C01 21/21, C02 7/15, C03 34/22, C04 21/22; all eight latest relay statuses are HTTP 200. C01 remains in runner evaluation after both Actor turns completed; its run archive and per-job 404 watchdog are active. The queue manager continues to own all four Guest slots.
- Queue snapshot 2026-11-25 00:58 UTC: C01 was recorded `COMPLETED_WITH_ISSUES` after both Actors ended at 21 tool calls and the runner repeated 404s fetching absent deliverables; the watchdog interrupted only the evaluator and released the Guest. C05 has now started automatically in the freed slot. C02/C03/C04 remain active (7/19, 40/22, 26/26 actions respectively); C06–C08 remain queued. C01's archived relay requests were HTTP 200 and at most one image/request.
- Queue snapshot 2026-11-25 00:59 UTC: C01 remains `COMPLETED_WITH_ISSUES`; C02/C03/C04/C05 are active (7/19, 43/22, 28/29, 0/0 actions), C06–C08 queued. The C05 live runner environment has been read back and points to the correct C05 staged task-assets root. C01 full-run relays made 22 requests per actor, all HTTP 200, with a maximum of one image in each request.
- Queue snapshot 2026-11-25 01:00 UTC: C01 and C02 are `COMPLETED_WITH_ISSUES` after both Actors ended without expected deliverables and repeated evaluator HTTP 404s were stopped by the watchdog. C03/C04/C05/C06 are active (50/22, 34/36, 1/1, 0/0 actions); C07–C08 queued. The older two run archives retain the actor logs and all screenshots; their model calls had HTTP 200.
- Resolved below: C08 bridge now normalizes its 0-23 checkpoint count to the 0.0-1.0 score scale. This batch was not rerun.

## 2026-11-25 — offline Oracle/bridge audit and re-evaluation

- **No Guest was started, no Agent trace was rerun, and no experiment was launched.** Only local bridge/Oracle code was edited; archived evaluator workspaces were regraded offline.
- CONC-04 bridge fix: both Actor A and Actor B downloads now preserve the expected `workspace/out_a/` and `workspace/out_b/` layout. Previously both branches flattened files into `workspace/`, so the Oracle looked in empty subdirectories.
- CONC-04 B10 fix: interaction evidence now passes at **8 or more qualifying operations total** (box drags with at least 3 pointer moves plus valid classification-key events), allowing retries/corrections during shared-GUI focus collisions instead of requiring exactly 8 of each.
- CONC-08 bridge fix: `C.result` now receives `clamp(raw_checkpoint_count / 23, 0, 1)` and records the raw count and denominator in evidence.
- Static audit of C01–C03 and C05–C07 found no matching flatten-to-root artifact-path defect and no unnormalized score return. Their existing bridge destinations align with their Oracle workspace paths; their `C.result` inputs are already normalized.
- Offline artifacts used: archived CONC-04 Actor A empty workspace/state and Actor B output files/state under `/tmp/conc04-eval-*`; archived CONC-08 Actor A workspace/state and Actor B `HR_Close.pptx` under `/tmp/conc08-eval-*`, plus the exact C08 source workbook from the run cache. Copies and the full machine-readable results are kept at `dashboard/reeval-input/` and `dashboard/data/offline-reeval-results.json`.
- CONC-04 Actor A remained 0/12 because its archived output workspace was empty. Actor B changed 0/12 → 4/12: B1, B10, B11, and B12 pass; B2–B9 still fail because the exported box geometry/labels do not meet Oracle truth. The score change is a corrected false negative for structure/interaction/render checks, not a completed annotation task.
- CONC-08 regrade: Actor A passed 6/23 = 0.2609; Actor B passed 7/23 = 0.3043 using the available deck and exact cached source workbook. **Actor B's `state.json` was not archived**, so state-dependent checks count as false; B's result is explicitly a partial-archive offline score, not an original emitted `result.json`.

### Eight-case score comparison (0–1 scale)

| Case | Before A/B | After A/B | Passed checks A/B (before → after) | Basis |
|---|---:|---:|---:|---|
| C01 | 0.0000 / 0.0000 | 0.0000 / 0.0000 | 0/14* / 0/14* → same | No original result; owner-recorded 0 for missing deliverables |
| C02 | 0.2500 / 0.0833 | same | 3/12 / 1/12 → same | Existing result |
| C03 | 0.0000 / 0.1000 | same | 0/10 / 1/10 → same | Existing result |
| C04 | 0.0000 / 0.0000 | 0.0000 / 0.3333 | 0/12 / 0/12 → 0/12 / 4/12 | Patched Oracle, archived output regraded |
| C05 | 0.0909 / 0.0909 | same | 1/11 / 1/11 → same | Existing result |
| C06 | 0.0000 / 0.0000 | same | 0/13 / 0/13 → same | Existing result |
| C07 | 0.0909 / 0.0455 | same | 1/11 / 1/22 → same | Existing result |
| C08 | — / — (A had 6 raw checks, not normalized) | 0.2609 / 0.3043† | 6/23 / — → 6/23 / 7/23† | Archived partial workspaces regraded; B state absent |

`*` C01's 0/14 is implied by the recorded missing-output 0 score; no original Oracle evidence file exists. For unchanged cases, pass counts are reconstructed from the archived normalized score and each Oracle's denominator; individual flags were not present in the archived summary. `†` C08 B is based on available archived artifacts and an empty state because the original B state file was not retained.

- Static dashboard refreshed at `dashboard/index.html`; it now shows before/after normalized scores, check counts, and available item-level C04/C08 details. Text payload is emitted with explicit UTF-8 metadata and Unicode-escaped JSON so Chinese display no longer depends on the JS file's transport encoding.
- Checks: CONC-08 `tests/test_conc08.py` passed (6 tests); edited Python sources compile. The local static server already listening at `http://127.0.0.1:8766/index.html` returned HTTP 200; it was not restarted.

## Targeted CONC-01 / CONC-05 service and frontend retry (2026-11-25)

- Fixed only `CONC-01/integration/service.py` and `CONC-05/integration/service.py`. C01 task pages/APIs now open without a cookie; the telemetry overlay uses a 1280×720 Guest-display minimum, and hover/evidence dimensions use the Guest screen size so the left Dock does not create a false narrow-window block. C05's loopback pages and APIs no longer reject the first unauthenticated request.
- Local validation: Python compilation passed; `audit_case_module.py` reported C01 7/7 PASS and C05 6/6 PASS; direct no-cookie HTTP smoke passed for both C01 pages, all four C05 pages, and representative write APIs. C01/C05 deterministic Gates 1–4 and fixture feasibility pass; careful-concurrency/real-tool Gate 5 remains pending the new Guest runs.
- Updated only the staged C01/C05 `service.py` files in their existing queue asset roots and verified their hashes and the four staged C05 application images.
- HealthCare `agent-queue-codex-v1` now has two scoped shared retries: `CONC-01-codex-shared-20261125T070224Z` and `CONC-05-codex-shared-20261125T070224Z`. Both use the persistent Codex + desktop/read-only Guest CLI harness, `gpt-6-sol`, actor/runner timeout 7200 seconds, and are `RUNNING`. Latest queue snapshot: C01 A/B had 9/9 non-screenshot actions (10/10 log rows) and C05 A/B had 10/10 non-screenshot actions (11/11 log rows); all four latest relay statuses were HTTP 200. Logs show branded Northstar Checkout/Telemetry and MiniCRM/TechWiki page titles rather than auth-error pages; corrected Guest service setup completed for both cases.
- C02, C03, C04, C06, C07, and C08 were not modified or requeued.
