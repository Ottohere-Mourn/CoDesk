# Professional shared-desktop pilot

`professional_shared.py` runs an A/B task pair against **one application instance,
one X11 display, and one shared native document**. Each agent has independent
model history and only its own task instruction. This is not two isolated Docker
desktops executing at the same time.

`parallel` starts both agents at a barrier. Inference and input are concurrent;
there is no input/batch mutex, automatic refocusing, or inter-agent communication.
`sequential` runs A then B in the same initial environment, with the same prompts
and per-agent budgets, as a matched scheduling control. The timeline mutex only
protects bookkeeping; it never covers input, screenshots, or network requests.
Screenshot capture uses unique temporary paths to avoid concurrent overwrite.

## Run on VM10

From `/data/yuke/paraGUI/CoDesk`, with existing host-only credentials:

```bash
/data/yuke/paraGUI/.test-venv/bin/python -u -m experiments.professional_shared \
  --dataset /data/yuke/paraGUI/authoring/professional-20261030T162043Z/work \
  --credentials /path/to/host-only-config.json \
  --out /data/yuke/paraGUI/trajectories/new-shared-run \
  --pair p3 --mode parallel --max-actions 300 --max-turns 90 --timeout 1500
```

Use a new output directory for each run. Change only `--mode sequential` and the
output directory for the scheduling control. Credentials and graders never enter
the desktop container; networking is disabled there. The collector does not run
Codex CLI or enable YOLO. GUI-only/console restrictions remain prompt rules plus
a desktop-only tool surface, not OS-level console blocking.

The paired QGIS tasks are risk classification/GeoJSON export (A) and a neutral
field-survey print layout/PDF/PNG (B), sharing the project and GeoPackage. The
other existing Blender and FreeCAD pairs are also supported.

## Evidence and evaluation

- `timeline.jsonl`: globally ordered observation, inference, input and completion
  records, with agent identity and global action IDs.
- `concurrency.json`: overlapping agent lifetimes and HTTP requests, host input
  dispatch overlap, action-order switches, errors, and potentially stale actions.
- `index.html`: interleaved screenshot replay in action-completion order. Each
  task also retains its independent trajectory replay and raw model records.
- `shared/workspace`: the actual shared files; each task's `workspace` is a copy
  of the **common final state**, not its own isolated completion state.
- `shared/evaluation`: one evaluation after both agents stop and the desktop is
  shut down. Both task scores refer to this same frozen state.

The stop/grade separation prevents evaluation from disturbing the remaining
agent. Shared results are not evaluated independently when the first agent stops.
The original six-check graders are unchanged. Screenshot/action provenance and
source/output hashes are checked, including the collector and support snapshots.
The offline reviewer also checks global action phases against each agent's action
log and confirms that both results describe the common frozen workspace:

```bash
python -m experiments.summarize_professional_shared /path/to/run \
  --dataset /path/to/original-authoring-package
```

Potentially stale actions count foreign input since the model's observation, or
foreign input in flight at observation/action time; this is exposure, not proof
of damage. Input overlap measures host dispatch intervals, not X-server event
timestamps. Both agents share an application, so window titles cannot identify
which agent owns focus. API throttling is logged separately from GUI errors.

A single pilot does not establish a success rate or causal effect. Earlier solo
data include only A tasks and different prompts/timing, so they are descriptive
references, not a matched A+B scheduling comparison. Preserve failed attempts.

```bash
python -m pytest -q tests/test_professional_shared.py tests/test_professional_trajectories.py
```
