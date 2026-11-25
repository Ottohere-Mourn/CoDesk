"""Shared setup and post-episode evaluation bridge for CONC-01."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from evaluation_examples.task_class import pg_common as C
from evaluation_examples.task_class.conc01_grade import evaluate as grade_workspace

ROOT = f"{C.HOME}/.local/share/paragui/conc01"
STATE = "/tmp/conc01-runtime/state.json"
URLS = ["http://127.0.0.1:18081/bootstrap", "http://127.0.0.1:18082/bootstrap"]
ASSETS = ["out_a/qa_viewport_report.json", "out_a/qa_375.png", "out_a/qa_768.png", "out_a/qa_1440.png",
          "out_b/ops_telemetry.json", *(f"out_b/ops_tab_{i}.png" for i in range(1, 7))]


def setup(sc, open_tabs=False):
    C.upload(sc, [("CONC-01/service.py", f"{ROOT}/service.py")])
    C.sh(sc, f"""mkdir -p {ROOT} /tmp/conc01-runtime /home/user/workspace/in_a /home/user/workspace/in_b /home/user/workspace/out_a /home/user/workspace/out_b
if ! curl -sf -m 1 http://127.0.0.1:18081/health >/dev/null; then
  setsid -f python3 {ROOT}/service.py --role A --port 18081 >{ROOT}/service-a.log 2>&1 < /dev/null
fi
if ! curl -sf -m 1 http://127.0.0.1:18082/health >/dev/null; then
  setsid -f python3 {ROOT}/service.py --role B --port 18082 >{ROOT}/service-b.log 2>&1 < /dev/null
fi
sleep 2
curl -sf -m 2 http://127.0.0.1:18081/health >/dev/null
    curl -sf -m 2 http://127.0.0.1:18082/health >/dev/null""")
    if open_tabs:
        # The reference viewport checks compare the browser's CSS outerWidth.
        # Force a 1:1 device scale on this fresh Guest so a 1920px desktop is
        # not exposed as a few hundred CSS pixels by a fractional-scale profile.
        C.sh(sc, "pkill -x chrome >/dev/null 2>&1 || true; pkill -x socat >/dev/null 2>&1 || true")
        sc.launch("exec google-chrome --remote-debugging-port=1337 --force-device-scale-factor=1", shell=True)
        C.open_chrome(sc, URLS)


def _fetch(env, out_root):
    workspace = Path(out_root) / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    for rel in ASSETS:
        dest = workspace / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            C.fetch(env, f"/home/user/workspace/{rel}", str(dest))
        except Exception:
            # Preserve partial evidence and let deterministic missing-file
            # checks score the incomplete actor output instead of aborting.
            continue
    state_path = Path(out_root) / "state.json"
    try:
        C.fetch(env, STATE, str(state_path))
    except Exception:
        pass
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = None
    return workspace, state


def _evaluate(env, actor):
    base = Path(os.environ.get("CONC01_EVAL_OUT", tempfile.mkdtemp(prefix="conc01-eval-")))
    out = base / f"actor-{actor}"
    out.mkdir(parents=True, exist_ok=True)
    workspace, state = _fetch(env, out)
    scores = grade_workspace(workspace, state)
    score = scores["actor_a" if actor == "a" else "actor_b"]
    return C.result(score, {k: v for k, v in scores.items() if k not in {"actor_a", "actor_b"}})


def evaluate_actor_a(env):
    return _evaluate(env, "a")


def evaluate_actor_b(env):
    return _evaluate(env, "b")


def evaluate_gate5(env):
    """Collect the on-Guest reference run used for the deterministic Gate 5 observation."""
    base = Path(os.environ.get("CONC01_EVAL_OUT", tempfile.mkdtemp(prefix="conc01-eval-")))
    out = base / "gate5"
    out.mkdir(parents=True, exist_ok=True)
    timing_path = out / "gate5_timing.json"
    C.fetch(env, "/tmp/conc01-runtime/gate5_timing.json", str(timing_path))
    observation = {}
    try:
        observation = json.loads(timing_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    if observation.get("schedule_complete") is True:
        workspace, state = _fetch(env, out)
        scores = grade_workspace(workspace, state)
        joint_pass = scores["joint_pass"] is True
        flags = scores.get("flags", [])
    else:
        joint_pass, flags = False, ["reference_schedule_incomplete"]
    evidence = {
        "joint_pass": joint_pass,
        "careful_conc_elapsed_s": observation.get("careful_conc_elapsed_s"),
        "conc_role_timeout_s": observation.get("conc_role_timeout_s", 3600),
        "overlap_s": observation.get("overlap_s"),
        "schedule_complete": observation.get("schedule_complete") is True,
        "errors": observation.get("errors", []),
        "reference_guest_replay": observation.get("reference_guest_replay") is True,
        "flags": flags,
    }
    (out / "gate5_guest_observation.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return C.result(1.0 if evidence["joint_pass"] and evidence["schedule_complete"] else 0.0, evidence)
