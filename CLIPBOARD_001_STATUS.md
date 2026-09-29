# Clipboard 001 implementation status

This is a partial executable implementation for task `CODESK-TB-CLIPBOARD-001`.
It does not change the frozen V1 taxonomy, old evaluator rules, or old experiment
artifacts. The registry remains `design_only` until the Guest and condition
promotion gates below pass.

## Implemented in this checkpoint

- `scripts/guest_clipboard_probe.py` samples the Guest X11 `CLIPBOARD` owner XID,
  advertised targets, UTF-8/STRING payload digest, local generation, active and
  focused window XIDs/titles, and sample duration. Payload bytes are not output.
- `swcub/clipboard_observer.py` validates samples, installs a run-scoped probe,
  tracks owner and payload changes separately, and attributes a logical actor
  only when a post-action copy/cut is bracketed and its digest matches that
  actor's independently specified source. An X owner XID is never treated as an
  Actor ID.
- `OSWorldSharedEpisode` accepts an optional hidden sampler and logs private
  observer events tagged with the source Actor. Samples are not added to the
  Actor observation. Where the accessibility tree supplies a focused editable
  node, its role/name/bounds are recorded without text content. Missing target
  evidence remains unknown.
- `swcub/tasks/clipboard_v1.py` contains fixed FODT/FODS seeds, initial-state
  readiness validation, actor-specific Solo/joint exact saved-state evaluation,
  proposed condition topology checks, and task specification.
- `ScriptedClipboardActor` uses normal GUI Ctrl+C/Ctrl+V/Ctrl+S actions. The
  Writer recopy path is a separate recovery control. No coordinator action
  rewrites a paste target or payload.
- Offline tests exercise event attribution, exposure/failure/recovery separation,
  exact ODF fixture parsing, actor action sequencing, private observation
  separation, and fail-closed topology validation.

## Critical instrumentation limitation

Reading X11 `TARGETS` and text requires requesting selection conversion from the
current owner (`xclip -o`). This can invoke the owner's normal request handler
and add timing. The code records probe duration and checks that the owner did not
change during a sample, but those checks do **not** establish non-perturbation.
An observer-on/off Guest control, including clipboard owner, copy/paste latency,
saved files, and screenshots, is still mandatory before causal use. If it changes
the task behavior or cannot read a stable digest, stop the mechanism experiment.

The existing accessibility trees sometimes report a focused editable node, but
application-specific target identity (Writer's destination paragraph or Calc's
cell address) has not been demonstrated against the current Guest. Window focus
alone is not treated as paste-target proof. If the target node does not expose
the required identity, `target_matches` must remain unknown; final-state errors
must not be over-attributed to clipboard replacement.

## Condition integrity

`validate_topology()` rejects MA-ID unless both Actors carry the same explicit
workspace-backend identity and distinct desktop and clipboard identities. The
existing Writer/Calc `ma_id` runner creates separate Guest workspaces; it is not
a valid implementation of this Clipboard 001 control and must not be reused or
relabeled. No same-backend / independent-X-session adapter has yet been proven.
MA-SD requires common workspace, desktop, and clipboard identities. Until both
topologies are available and verified, paired conditions remain unvalidated.

## Validation run

Run only offline, non-Guest tests:

```bash
pytest -q tests/test_clipboard_observer.py tests/test_osworld_adapter_contract.py \
  tests/test_runner_v1_config.py tests/test_task_registry_v1.py
python -m py_compile swcub/clipboard_observer.py swcub/osworld_adapter.py \
  swcub/tasks/clipboard_v1.py scripts/guest_clipboard_probe.py
```

The unit tests use synthetic snapshots and a signature-compatible Desktop stub.
They are not a Guest launch, LibreOffice execution, clipboard probe, or real
application validation.

## Status and next gates

| Component / condition | Status |
|---|---|
| Probe syntax and offline snapshot logic | Implemented; offline tested |
| Hidden event logging and Actor observation separation | Implemented; stub tested |
| ODF seed parsing and exact evaluator | Implemented; offline fixture tested |
| Real X11 owner/payload observer fidelity | Unvalidated |
| Observer-on/off non-perturbation | Unvalidated |
| Guest Writer/Calc setup, save/reopen, reset | Unvalidated; no task runner integrated yet |
| Solo Writer and Solo Calc | Unvalidated |
| MA-ID same backend with separate X clipboard sessions | Design/adapter gap; unvalidated |
| MA-SD scripted ordinary copy/paste and recovery | Action actor/evaluator code exists; Guest unvalidated |
| Qwen Solo / dual-agent Writer+Calc | Not run; independent existing path preserved |

The host load average observed during this work was approximately `343 / 314 /
304` over 1/5/15 minutes, with all 2 GiB swap occupied. No Guest, model worker, or
other user's process/resource was started, stopped, or modified.
