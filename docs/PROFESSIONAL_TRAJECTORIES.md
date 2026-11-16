# Professional software GUI trajectories

The 2026-11-02 pilot contains six recorded solo attempts on three tasks: Blender
lamp geometry and STL export, FreeCAD machining and STEP/SVG export, and QGIS
risk analysis and GeoJSON export. Each task was attempted once, interrupted by
HTTP 429, then retried from its original inputs with a longer cooldown policy.

See the [combined report](../runs/trajectories/PROFESSIONAL_20261102.md) and
[browser replay index](../runs/trajectories/professional-20261102.html).
The retries scored 1.0, 5/6 and 1.0 respectively. FreeCAD's drawing check rejects
its native SVG path representation and diameter glyph; the report preserves the
original score and provides a separate artifact review.

## Collect a new run on VM10

The collector requires Python with `requests`, Docker, the existing
`paragui/professional-authoring:20261030` image, and the authoring package.
Each task gets a fresh, network-disabled container with only its input workspace
mounted. The original task text and input reference image are allowed; reference
solutions and graders stay outside the agent container. The evaluator uses a
separate container after the desktop stops.

From the CoDesk checkout on VM10:

```bash
python3 experiments/professional_trajectories.py \
  --dataset /data/yuke/paraGUI/authoring/professional-20261030T162043Z/work \
  --credentials /path/to/host-only-model-config.json \
  --out /data/yuke/paraGUI/trajectories/new-unique-run \
  --tasks p1a p3a p2a --access gui \
  --max-actions 300 --max-turns 90 --timeout 1500
```

The credentials JSON has `base_url`, `api_key`, `model`, and `reasoning_effort`
fields. The pilot used `gpt-6-astra` / `high`. Use an authorized existing config;
the supplied archive contains no credentials. The output directory must be new.
Tasks run one after another, each on its own fresh desktop. `--timeout` is the
agent wall-clock budget per task; startup and evaluation take additional time.

This collector is a Responses API tool loop. It does not invoke the Codex CLI or
enable YOLO. Its tools expose mouse, keyboard, screenshots, and a finish action.
The GUI-only rule prohibits script consoles in the prompt; it is not an OS-level
console block. Normal QGIS field expressions and FreeCAD parameter expressions
are allowed. Inspect actions and screenshots when auditing this restriction.

## Inspect and verify a run

```bash
python3 experiments/summarize_professional_trajectories.py \
  /data/yuke/paraGUI/trajectories/new-unique-run \
  --dataset /data/yuke/paraGUI/authoring/professional-20261030T162043Z/work
```

This generates `REPORT.md`, `index.html`, and `trajectory-summary.json`, and
checks input and output hashes, the collector snapshot hash, expected task
results, screenshot validity, response counts, and action order within each
model tool call. Without `--dataset`, input verification is explicitly omitted.
These checks establish consistency of the recorded files, not signed provenance.

Each trial has an offline `trajectory.html`: move its slider to inspect the
initial desktop and every action. `actions.jsonl` records focus before and after,
timing, model turn/call IDs, and errors. Every primitive gets a screenshot, while
the model receives only the last screenshot of each batch. Requests retain the
most recent three images and all text/tool history; image data is archived as
relative paths. Original response JSON and request-attempt timing remain available.

`result.json` contains the stop reason and independent scores. `completed` means
the model stopped answering, not that every requirement passed. Request retries
never replay desktop actions. Failed attempts and their partial workspaces are
kept independently of retries. The paired B-task score is diagnostic only: the
agent in these runs received only task A.

The three B tasks, shared-desktop concurrency, and OSWorld task registration are
outside this pilot. Scores use six checks per task from the authoring package;
they do not constitute comprehensive visual or engineering acceptance.

## Shared-desktop follow-up

The separate [shared-desktop collector](../experiments/PROFESSIONAL_SHARED.md)
runs a paired A/B task with independent agents on one application and project.
It supports barrier-started `parallel` and same-desktop `sequential` controls,
records cross-agent timing and observation exposure, and evaluates the common
final files only after both agents stop. These runs are separate from the solo
archive described above.

The first QGIS A/B parallel run finished on 2026-11-02. Its common-final-state
scores are A **1/6** and B **5/6**, with 261 actions and 263 screenshots. See the
[review and limitations](../runs/trajectories/professional-shared-p3-parallel-20261102T061307Z/REVIEW.md)
and [interleaved replay](../runs/trajectories/professional-shared-p3-parallel-20261102T061307Z/index.html).
The run records a stale-observation `Alt+F4` targeting a different active window;
33 HTTP 429 responses also affect interpretation. No matched sequential control
has been collected yet.
