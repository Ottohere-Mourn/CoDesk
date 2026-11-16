# Professional task candidates v2

This is a new, original synthetic candidate set informed by professional-software
benchmarks. It is **not an official benchmark subset**. Read
`../../docs/PROFESSIONAL_BENCHMARK_RESEARCH_20261102.md` for sources and observed
GUI/code trajectory differences.

The separate `../professional_v3/README.md` describes the 2026-11-03 hard-hybrid
and concurrency design for p10–p12. p10 has native authoring validation and an
active first calibration; p11/p12 remain unbuilt. None replaces these candidates
or establishes calibrated difficulty or completed agent outcomes.

## Interaction policy (updated 2026-11-03)

The main condition is **hybrid GUI+CLI/code**, not GUI-only. Terminal commands,
application consoles, scripts, `bpy`, PyQGIS and other application APIs are
allowed inside the experiment containers. Agents choose their workflow; the
catalog's GUI and hybrid phases are suggestions, not required action sequences.
GUI-only is an explicitly labelled ablation, not a benchmark-wide restriction.

Two agents still share the desktop, live project and task filesystem. Auxiliary
CLI processes are allowed, but separate private final projects are not a
substitute for the shared artifact. Avoid stale whole-file saves, preserve the
other role's semantic edits, and verify that the live and saved state agree.
Programming does not grant access to graders, references, credentials or host
files. No host/VM Codex permission settings may be relaxed.

The native p1–p3 runner now accepts `--interaction-mode hybrid` (the default),
with recorded target-container shell actions for both Codex and Freehand.
This does **not** register p4 or turn the scripted references into agent runs.

## Readiness

- `catalog.json` defines six pairs (twelve role tasks), semantic ownership,
  optional GUI/hybrid phases, provenance, outputs and six checks per role.
- **p4 Blender** has a native scene builder, two scripted reference edits, a
  fresh-process inspector, a semantic grader and container validation driver.
- **p5–p7** are specifications only. Their applications exist in the current
  professional image, but their new native assets and graders are not built.
- **p8–p9** additionally require KiCad/CloudCompare runtime and harness support.
- None is registered in the existing p1–p3 native/shared runners. Do not select
  p4 using an old runner or silently substitute it for p1.
- Agent trajectories: **zero**. Scripted references and GUI reopen screenshots
  are authoring validation, not successful GUI agent runs.

p4 is a small controlled starting case, not a claim of expert-level or
long-horizon difficulty. The more involved candidates remain explicitly unbuilt.

The system under test remains two independent agents on one desktop, application
process and project. A/B goals must commute semantically even though focus,
selection, mode, dialogs and editor state can interfere during execution.

## Validation record: 2026-11-02

The fresh r2 validation finished at **16:22:52 UTC**, using Blender **3.4.1**
inside a non-root, network-disabled, read-only-root Docker container. Source
and artifact hashes were verified after copying the outputs back locally.
All 12 validation conditions passed, including both GUI reopen checks. The
initial and combined GUI screenshots were visually inspected; frame-31 renders
show the intended lid pose and independent instrument material changes.

| Scripted condition | A | B |
| --- | --- | --- |
| Initial | 3/6 | 2/6 |
| A only | 6/6 | 2/6 |
| B only | 3/6 | 6/6 |
| A then B | 6/6 | 6/6 |
| B then A | 6/6 | 6/6 |

Initial credit comes from preservation/native-validity checks, not completed
editing. These are **reference scores, not agent scores**. The first r1 run
passed semantic checks but captured the initial GUI before it had painted
(a blank gray window). Its original files/manifest remain preserved. A bounded
nonblank-content readiness check was added; the fresh r2 run replaces neither
that history nor any existing p1–p3 experiment.

Local evidence: `../../runs/authoring/professional-v2-20261102-p4-r2/validation/manifest.json`.
VM evidence: `/data/yuke/paraGUI/research/professional-v2-20261102-p4-r2/work/validation/`.
VM image ID: `sha256:619def5ca3f9ab4d238f43ad0568ee0b334814c77cdfc2bda86ad036d168d618`.
The local source/test suite passes **102 tests** (12 newly added in this round).

Inputs-only archive:
`../../runs/authoring/professional-v2-20261102-p4-r2/p4-inputs-only.tar.gz`.
It contains only the initial `.blend`, two role prompts, pair metadata and a
hash manifest; no grader, reference solution or inspector report is included.
That archive is a frozen **2026-11-02 GUI-only authoring snapshot**. For a new
hybrid run, reuse only its native input and copy the current `p4/task_a.md`,
`p4/task_b.md` and `p4/pair.json` into a fresh inputs-only bundle with new hashes.
Do not silently edit or relabel the archived prompts or validation manifest.

## Validate p4 inside Docker

Use the existing image on VM10; no model, credentials or Codex configuration is
needed. Run Docker normally from the host. Do not enable unrestricted Codex on
the host or VM. `SOURCE` must contain this directory, and `OUTPUT` must be a new,
writable directory. The scripts reject execution outside Docker.

```bash
SOURCE=/absolute/path/to/professional_v2
OUTPUT=/absolute/path/to/new-authoring-output
mkdir -m 700 "$OUTPUT"
docker run --rm --network none \
  --user "$(id -u):$(id -g)" --cpus 2 --memory 6g --pids-limit 512 \
  --shm-size 512m --cap-drop ALL --security-opt no-new-privileges \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=1g,mode=1777 \
  -e HOME=/tmp -e XDG_RUNTIME_DIR=/tmp/runtime -e XDG_CACHE_HOME=/tmp/cache \
  -v "$SOURCE:/authoring:ro" -v "$OUTPUT:/work:rw" \
  paragui/professional-authoring:20261030 \
  bash -c 'mkdir -m 700 /tmp/runtime; exec python3 /authoring/validate_blender.py /work/validation --gui'
```

`validation/` must not already exist. Preserve failures and use a new output
directory on retry. The validator checks:

1. The seed is not solved, but its preservation checks may already pass.
2. A-only reaches A's target while keeping B's material inputs unchanged.
3. B-only reaches B's target while keeping A's motion inputs unchanged.
4. A→B and B→A both pass and produce identical inspected semantic state.
5. Wrong color, missing editable keys and deleted-asset negative controls fail
   the corresponding checks or integrity gates. These are inspector-state
   mutations, not adversarial edits of binary `.blend` files.
6. Initial and combined native files render and reopen in the real Blender GUI
   when `--gui` is supplied. Inspect the screenshots visually as a separate step.

The manifest records checks, gated and raw scores, timestamps, software version,
file hashes and source hashes. `.blend` binary equality is not required: Blender
may serialize the same semantic state differently. The actual validated version
is recorded rather than assumed from a floating image tag.

## Input/answer separation

Only `validation/input/HingeStudio.blend` belongs in the agent's input workspace.
Give role A `p4/task_a.md` and role B `p4/task_b.md` through their separate prompts.
The entire `validation/` directory **must not** be mounted into an agent container:
it also holds reference projects, inspector reports, grades and authoring logs.
Likewise, do not expose this source directory, the catalog's checks or the grader.

The project is saved in place by both agents. The grader reopens their common
final file in a separate container and compares it to the trusted initial
snapshot. `grade_blender.grade(final_state, baseline_state)` returns six checks
per role and independent preservation gates. Geometry, fixed scene state, shader
connections, unrelated shader inputs and external dependencies are checked.
A gate failure makes both gated scores zero while retaining diagnostic raw scores.
This limited structured inspector is not a comprehensive anti-cheating proof.

The evaluator, not either agent, renders the combined final scene. Thus B's
deliverable does not depend on A finishing an animation first. Color checking
converts the specified sRGB hex values to Blender's linear shader values;
entering sRGB channel fractions directly as linear values is not equivalent.

Before promotion, add runtime registration without changing frozen p1–p3,
then run real hybrid solo A/B pilots, same-desktop sequential controls in both
orders, and the shared-desktop parallel condition. Run GUI-only separately if
needed as an ablation. Measure task and joint success separately from wall time,
API throttling and process errors. Record CLI output/exit codes, GUI actions,
console-mediated code, and live/file-state conflicts without equating a shell
command with a click or attributing all interference to GUI focus.
