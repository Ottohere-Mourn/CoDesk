"""Pair setup and blind evaluation bridge for CONC-04."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from evaluation_examples.task_class import pg_common as C
from evaluation_examples.task_class.conc04_grade import grade

ROOT = f"{C.HOME}/.cache/paragui/conc04"
STATE = "/tmp/conc04-runtime/state.json"
FILES = [("CONC-04/service.py", f"{ROOT}/service.py"),
         *[(f"CONC-04/guest/in_b/charts/chart_{i}.png", f"{ROOT}/charts/chart_{i}.png") for i in range(1, 5)]]


def setup(sc, actor: str):
    C.upload(sc, FILES)
    C.sh(sc, f"""mkdir -p {ROOT}/charts /tmp/conc04-runtime /home/user/workspace/in_a /home/user/workspace/in_b/charts /home/user/workspace/out_a /home/user/workspace/out_b
cp {ROOT}/charts/*.png /home/user/workspace/in_b/charts/
if ! curl -sf -m 1 http://127.0.0.1:18091/health >/dev/null || ! curl -sf -m 1 http://127.0.0.1:18092/health >/dev/null; then
  setsid -f python3 {ROOT}/service.py --chart-root {ROOT}/charts --out-root /home/user/workspace --state {STATE} >{ROOT}/service.log 2>&1 < /dev/null
fi
for i in $(seq 30); do curl -sf -m 1 http://127.0.0.1:18091/health >/dev/null && curl -sf -m 1 http://127.0.0.1:18092/health >/dev/null && break; sleep 1; done
curl -sf -m 2 http://127.0.0.1:18091/health >/dev/null && curl -sf -m 2 http://127.0.0.1:18092/health >/dev/null""")
    # Distinct Chrome profiles provide two real overlapping windows. The
    # second window is intentionally offset but still covers the central work area.
    if actor == "a":
        sc.launch("exec google-chrome --remote-debugging-port=1337 --user-data-dir=/tmp/chrome-conc04-a --window-size=1280,840 --window-position=80,90 http://127.0.0.1:18091/", shell=True)
    else:
        sc.launch("exec google-chrome --remote-debugging-port=1338 --user-data-dir=/tmp/chrome-conc04-b --window-size=1280,840 --window-position=300,150 http://127.0.0.1:18092/", shell=True)


def _workspace(env, actor: str, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    if actor == "a":
        for name in ("arch_flow.json", "arch_flow.png"):
            try:
                C.fetch(env, f"/home/user/workspace/out_a/{name}", str(out / "workspace" / "out_a" / name))
            except Exception:
                pass
    else:
        for name in ("anomaly_labels.json", *(f"chart_{i}.png" for i in range(1, 5))):
            try:
                C.fetch(env, f"/home/user/workspace/out_b/{name}", str(out / "workspace" / "out_b" / name))
            except Exception:
                pass
    state_path = out.parent / "state.json"
    try:
        C.fetch(env, STATE, str(state_path))
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        state = {}
    return state


def _evaluate(env, actor: str):
    base = Path(os.environ.get("CONC04_EVAL_OUT", tempfile.mkdtemp(prefix="conc04-eval-")))
    out = base / f"actor-{actor}"
    workspace = out / "workspace"
    state = _workspace(env, actor, workspace)
    result = grade(workspace, state)
    (out / "checks.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    key = "actor_a" if actor == "a" else "actor_b"
    return C.result(result[key], {"checks": result["checks"][key], "flags": result["flags"],
                                  "aborted_drag_count": state.get("aborted_drag_count", 0),
                                  "misrouted_key_count": state.get("misrouted_key_count", 0)})


def evaluate_actor_a(env):
    return _evaluate(env, "a")


def evaluate_actor_b(env):
    return _evaluate(env, "b")
