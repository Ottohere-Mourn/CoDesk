# Case 4 Lite v1.0.0: Guest controls and desktop-topology comparison

Branch: `codex/case4-hardening`. Frozen task, fixture, role instructions, Oracle, `gpt-6.1-sol` medium, and 15 desktop calls per actor. The comparison runs A and B concurrently. Raw runs and overlays remain uncommitted and preserved. Scripted controls use the actual KVM Guest and GUI, without model calls.

## Engineering controls

`case4-v100-control-shared-positive-20261031b` is a valid positive control: GUI Kdenlive project repair and VS Code manifest save; all Oracle checks pass. A fresh Guest reopens both saved files and reproduces the native project parse and byte hashes. `case4-v100-control-shared-negative-20261031c` changes only the manifest answer: the video checks pass, `asset_manifest_saved` fails, and the fresh Guest reopens the same wrong saved manifest. Both runs end in `RESET_VERIFIED` with pristine baseline hashes. Earlier control attempts that failed before Oracle due the wrong base image, concurrent slow boot, or editor focus are retained as infrastructure/control diagnostics and are not counted as controls.

The pair runner now records actor validity, business Oracle, evidence/evaluation faults, reset fault, and Guest cleanup separately. Scored workspace files are archived under each run's `pre_reset` before the owned reset. A bounded setup diagnostic records Kdenlive/editor window state and error logs. The task and Oracle criteria were not relaxed.

## Environment and cohort integrity

The HDD base image and overlay on `/mnt/raid1` suffered sustained I/O stall. `case4-v100-repeat-shared-20261031a` failed before model release because VS Code did not open; `case4-v100-shared-setup-diagnostic-20261101a` failed before model release with Kdenlive in uninterruptible disk wait. Both are `INFRA_FAIL`, not business FAIL. The HDD Isolated run `case4-v100-repeat-isolated-20261031a` is a valid business FAIL: A saved the correct manifest but B exhausted 15 calls with the wrong V1/V2 clips. It remains separate from the SSD cohort.

The SSD copy has the same SHA-256 as the HDD native image: `bed3b0bab436abfd6c5d11c3fe503f4d2f622eb23c5b05c6ebc536d15025180d`. `case4-v100-ssd-setup-20261101a` passed full Guest, Kdenlive, and editor setup in about 100 s (HDD diagnostic took about 563 s and failed). All SSD comparison arms use the same SSD image and fresh SSD overlays. SSD comparison plans were committed before model calls.

| SSD run suffix | Isolated | Shared | Shared+Lock |
| --- | --- | --- | --- |
| `20261101a` | PASS, A8/B9, 430.5 s wall | FAIL, A15/B7, 371.2 s wall; only manifest failed | PASS, A15/B12, 396.0 s wall |
| `20261101b` | PASS, A8/B8, 415.4 s wall | FAIL, A15/B15, 443.6 s wall; manifest and video failed | MODEL_INVALID, A8 timeout/B6 API error, 1930.5 s wall; partial Oracle FAIL is not a valid business result |

Every SSD run has scored Guest artifacts, Oracle, and verified reset. The second locked run has an invalid model episode: A timed out at 1800 s, B exited after API stream errors, and the relay recorded two `ConnectionError` responses after about 304 s each. Its business Oracle scored the incomplete files FAIL, but it cannot enter the valid PASS/FAIL rate. The older HDD-era v1.0.0 model runs remain useful mechanism evidence: `case4-lite-manifest-isolated-20261030c` PASS A11/B8, `case4-lite-manifest-shared-20261030a` FAIL A10/B6, and two locked Shared runs `...shared-locked-20261030a/b` FAIL. They are not pooled into SSD success rates because startup/storage conditions and lock telemetry differ.

## GUI interference and lock mechanism

The first SSD Shared FAIL repaired the video project but left the manifest unsaved. A opened VS Code at action 5; B's action 3 returned the foreground to Kdenlive. A's action 6 clicked while Kdenlive was foreground, action 9 `HOME` also landed in Kdenlive, and subsequent editor recovery consumed calls. A typed the correct manifest at action 15 but reached the call limit before `Ctrl+S`; screenshot `actor_runs/A/A/shots/015.png` shows the dirty VS Code tab. The second SSD Shared FAIL has an observed 0.351 s overlap between A action 6 and B action 4; A's action 9 `Ctrl+O` opened a Kdenlive dialog instead of the editor's file dialog. Both agents exhausted 15 calls and neither final artifact met the task.

The first SSD locked Shared run had no overlapping input intervals, and all 27 logged tool calls sampled atomically. Total measured lock wait was 2.956 s (A 1.542, B 1.414), under 1% of its 396.0 s total wall time. Yet B action 7 `Delete` landed in VS Code and dirtied the manifest, while A action 12 text input landed in Kdenlive. The agents recovered: A saved the right manifest at action 15, B saved the right video at action 12, and Oracle passed. The second locked run also had no overlapping input intervals and still misrouted B action 5 `Delete` to VS Code and A action 7 `Home` to Kdenlive. It had only 0.876 s measured lock wait before the API fault and actor timeout. Thus the per-action lock prevents simultaneous inputs but does not preserve foreground state across calls; the first run's PASS does not prove the lock caused recovery. Total wall times include unequal model and setup time, so they are not a causal measure of lock overhead.

The valid SSD rates are Isolated 2/2 PASS, Shared 0/2 PASS, Shared+Lock 1/1 PASS with one additional API-invalid locked run. The Isolated/Shared gap and repeatable shared-GUI focus interference are supported in this small cohort. Shared+Lock failure is not repeatable as a simple claim; its mechanism remains vulnerable to misrouting even when Oracle passes. A focus-revalidation ablation was not run in this cohort, to keep the frozen three-arm comparison and Case 2 work prioritized.
