# Freehand on VM10

`freehand_vm10.py` connects oscombo's shared-desktop runner to the existing
`mini-harness/eval_osworld/agent.py` adapter and Freehand runtime. The runtime and
adapter are copied from `~/code/mini-harness` into the experiment's own directory;
their hashes are recorded in `deployment-manifest.json`.

The initial pilot uses `bingCalcSum` from `lists/osworld1_combos.txt`: Chrome's
default search engine and a Calc revenue/expense summary. Both agents start from
oscombo's parallel barrier, receive only their own task instruction, and share one
desktop. The original task definitions and evaluators are used unchanged.

## Paths and launch

Connect with `ssh gpu48-jump 'ssh cpu10 …'`. On VM10:

- Project: `/data/yuke/paraGUI/CoDesk`
- Existing OSWorld checkout and Python environment:
  `/data/yuke/osworld-freehand/source`
- Frozen runtime: `/data/yuke/paraGUI/runtime/freehand`
- Existing OSWorld adapter: `/data/yuke/paraGUI/runtime/mini_osworld/agent.py`
- Host credentials: `/data/yuke/paraGUI/private/api.json` (mode `0600`)
- Latest run pointer: `/data/yuke/paraGUI/active_run.json`

The credentials file contains `base_url`, `model`, `api_key`, and
`reasoning_effort`. It is outside the code checkout and is never included in the
guest bundle or deployment manifest. The host's Freehand gateway adds upstream
authentication; each guest agent receives its own temporary gateway URL.

```bash
cd /data/yuke/paraGUI/CoDesk
/data/yuke/osworld-freehand/source/.venv/bin/python -u \
  -m experiments.freehand_vm10 \
  --out /data/yuke/paraGUI/runs/<new-run-name> --timeout 1800
```

The pilot launcher uses a transient systemd service so the run survives SSH
disconnects. Its exact unit and output directory are in `active_run.json`.

## Interpretation and artifacts

The guest has 4 vCPUs and 8 GiB RAM, with a 10 GiB Docker memory limit. Its base
image is mounted read-only. Containers carry the `mini-harness.project=paragui`
label and per-run label; scratch disks are under this project's `vm-storage/`.

Freehand retains its Bash, file, script, and GUI capabilities inside the guest.
The model can edit its own session's context, configuration, and harness source.
The initial budget is 1000 model turns with four recent images per request. The
host enforces the separate `--timeout` limit for each agent.

`result.json` contains the original evaluator scores and each agent's completion
status. `agentA/` and `agentB/` contain API usage, gateway traces, and collected
guest trajectories. `start.png` and `end.png` capture the shared desktop. Initial
API validation, test results, source hashes, and container records accompany the
run. A model claiming completion is distinct from passing the task's evaluator.

The adapter's `steps` count successful model responses, not individual desktop
actions. Focus-before-action measurements are unavailable, so these runs cannot
report oscombo's focus-interference metric. This Freehand configuration should
also be distinguished from a harness restricted to GUI tools.

Validation on VM10 uses the project's separate test environment:

```bash
/data/yuke/paraGUI/.test-venv/bin/python -m pytest -q
```
