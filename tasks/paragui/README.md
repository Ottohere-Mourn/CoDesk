# paraGUI task pairs

One user, one Ubuntu desktop, **two computer-use agents that are each given one chore at the same time**. The two
chores are unrelated from the user's point of view (instructions never mention another assistant), but they
naturally touch the **same live thing**: the same running application instance or session, plus shared files. Each
task is graded by its own checker with partial credit; run the pairs alone, one after the other and at the same
time (`python -m oscombo run --mode solo|sequential|parallel`).

| pairs | family | shared live resource |
|---|---|---|
| c1 c2 c4 c5 c6 | round 1 (revised) | a workbook, the Downloads folder, one Thunderbird, a slide deck, a git repo |
| o1–o4 | F1 office documents | one open LibreOffice document |
| m1–m4 | F2 mail / calendar | one Thunderbird (folders, filters, calendar, contacts) |
| w1–w4 | F3 browser + intranet app | one Chrome window and one logged-in web-app session |
| d1–d4 | F4 developer | one VS Code window, a git working copy, a running dev server |
| f1–f4 | F5 files / media | shared folders, scans, images, media files |
| x1–x4 | F6 cross-app | Thunderbird + an intranet web app + office files |
| a1–a6 | attack round 1 | built to stay hard under per-harness defenses (`ATTACK_DEFENSE.md`) |

`python -m oscombo tasks list` prints every pair with its two task specs; `lists/paragui_v1_combos.txt` and
`lists/paragui_attack_combos.txt` are ready for `python -m oscombo matrix`.

## Install

```bash
source env.sh                                  # OSWORLD_DIR, the OSWorld venv python on PATH
python -m oscombo tasks install                # or: --pairs w1 m2
export PARAGUI_TASK_ASSETS=~/.cache/oscombo/paragui/assets
python -m oscombo run --mode parallel --tasks v2/pgw1reply v2/pgw1triage --policy openai-cua --model <m> \
    --max-steps 150 --out runs/w1-par
```

`install` copies `task_pg*.py` and `pg_*.py` into `$OSWORLD_DIR/evaluation_examples/task_class/` and runs
`build_assets.py`, which writes every pair's assets and `expected.json` deterministically (fixed seeds) into
`$PARAGUI_TASK_ASSETS/<pair>/`. The builders need the OSWorld venv (PIL, openpyxl, python-docx, python-pptx,
PyMuPDF, pypdf, ...). Mail pairs start from the public OSWorld blank Thunderbird profile (downloaded once).
Ground truth stays on the host: setups upload only the task's input files.

These tasks are long (a strong agent needs 30–60+ GUI steps alone): use a large `--max-steps`; the step harness
restarts the model conversation every `chain_steps` predictions with a progress note (`--opt chain_steps=40`).

## Files of pair `<p>`

| file | content |
|---|---|
| `build_<p>.py` | `build(out_dir)`: all assets + `expected.json`, deterministic (pairs c1–c6 are in `build_assets.py`) |
| `pg_<p>.py` | `setup(sc)` shared by both tasks (idempotent: it runs once per task in a dual run) and `evaluate_<a>(env, dest)`, `evaluate_<b>(env, dest)` returning `{"score", "checks"}` |
| `task_pg<p><a>.py`, `task_pg<p><b>.py` | thin OSWorld 2.0 task classes (id, instruction, related apps, evaluate call) |
| `app_<p>.py` | single-file stdlib intranet web app (`http.server` + `sqlite3`, cookie login), started in the Guest |
| `spec_<p>.md` | both user requests verbatim, persona, shared resources, expected contention, provenance, grading checklist, reference solution, expected step count |

Shared helpers: `pg_common.py` (upload, Guest shell, fetch, web apps, Chrome with remote debugging, Thunderbird,
results), `pg_mcommon.py` (mail/calendar parsing), `pg_olib.py` (office documents), `pg_dlib.py` (git repos),
`pg_fimg.py` (images), `pg_xcommon.py` (cross-app); builder libraries `lib_*.py`.
`tools/build_index.py`, `tools/analyze_v1.py` and `tools/dump_run.py` index, summarise and dump runs (both-pass =
both tasks score ≥ 0.8).

The specs mention offline self-tests (`lib_*test*.py`, reference solutions `lib_dref_*.py`) that were run while
authoring the pairs: a scripted reference solution scores 1.0 for both tasks in both orders, the pristine state
≤ 0.2. Those harnesses depend on the authoring host and are not part of this repository.

## Quality bar for new pairs

Each task must be:
1. **Realistic**: a concrete persona and a request a real person would send, with the details real requests have
   (a policy, exceptions, names, dates, amounts); the spec gives its provenance.
2. **Long-horizon**: ≥ 30–60 GUI steps for a strong agent working alone; ≥ 2 applications; several deliverables
   (files + application state + a short report/message).
3. **GUI-required** for at least one substantial part: text that exists only as pixels (scans, charts), data only
   visible through a logged-in web UI (the agent is not told the db path), application-internal state (Thunderbird
   filters/tags/calendar, Chrome settings, LibreOffice tracked changes/comments/styles, VS Code settings).
4. **Graded strictly and robustly**: 8–20 sub-checks with partial credit plus hard caps; cross-check against
   application state so faking a file is not enough; never require exact prose.
5. **Feasible**: a competent human finishes each task alone in 15–40 minutes; both tasks complete in either order
   when run one after the other (task B's checker accepts the world after task A's legitimate changes); no
   zero-sum designs.

The pair must create **natural contention**: both tasks work in the same Thunderbird main window, the same Chrome
window and web-app session, the same open LibreOffice document, the same repo / dev server, or one task's correct
work changes data the other must read. Round 1 showed that pairs sharing only *files* rarely collide (agents solve
them with scripts in a terminal); pairs sharing a *running app with internal state* do.

Setup rules: `setup(sc)` runs twice in a dual run, so anything stateful must be guarded (start apps/servers only if
not running, extract profiles once; see `pg_common.start_thunderbird`, `start_webapp`, `open_chrome`). Keep assets
small (< 30 MB per pair). Web apps bind 127.0.0.1 on port 81xx (xx = pair number), take `--db PATH --port N`, and
both tasks normally log in as the same user (sharing one browser session is the point).

Guest: Ubuntu 22.04 GNOME, 1920×1080, user `user`, sudo password `osworld-public-evaluation`, python3, Chrome,
Thunderbird 115, VS Code, LibreOffice 7.3, GIMP, VLC, Nautilus, gnome-terminal, gedit. Without KVM everything is
slow (app start 10–60 s): do not design around animations or timing.
