"""Shared Guest setup and deterministic post-episode checks for CONC-03."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from evaluation_examples.task_class import pg_common as C
from evaluation_examples.task_class.conc03_grade import grade


ROOT = f"{C.HOME}/.cache/paragui/conc03"
STATE = "/tmp/conc03-runtime/state.json"
URL = "http://127.0.0.1:18085/bootstrap"
FILES = [
    ("CONC-03/service.py", f"{ROOT}/service.py"),
    ("CONC-03/guest/in_a/receipts/receipt_EXP-401.png", f"{ROOT}/guest/in_a/receipts/receipt_EXP-401.png"),
    ("CONC-03/guest/in_a/receipts/receipt_EXP-402.png", f"{ROOT}/guest/in_a/receipts/receipt_EXP-402.png"),
    ("CONC-03/guest/in_a/receipts/receipt_EXP-403.png", f"{ROOT}/guest/in_a/receipts/receipt_EXP-403.png"),
    ("CONC-03/guest/in_b/safety_spec.txt", f"{ROOT}/guest/in_b/safety_spec.txt"),
    *[(f"CONC-03/guest/in_b/icons/{name}", f"{ROOT}/guest/in_b/icons/{name}")
      for name in ("icon_helmet.png", "icon_hazard.png", "icon_exit.png")],
    ("CONC-03/guest/out_b/Safety_Brief.pptx", f"{ROOT}/guest/out_b/Safety_Brief.pptx"),
]


def setup(sc, open_chrome=False):
    C.upload(sc, FILES)
    deck = "/home/user/workspace/out_b/Safety_Brief.pptx"
    C.sh(sc, f"""mkdir -p {ROOT} /tmp/conc03-runtime /home/user/workspace/in_a/receipts /home/user/workspace/in_b/icons /home/user/workspace/out_a /home/user/workspace/out_b
if [ ! -f /tmp/conc03-runtime/ready ]; then
  cp {ROOT}/guest/in_a/receipts/*.png /home/user/workspace/in_a/receipts/
  cp {ROOT}/guest/in_b/safety_spec.txt /home/user/workspace/in_b/safety_spec.txt
  cp {ROOT}/guest/in_b/icons/*.png /home/user/workspace/in_b/icons/
  cp {ROOT}/guest/out_b/Safety_Brief.pptx {deck}
  if ! curl -sf -m 1 http://127.0.0.1:18085/health >/dev/null; then
    setsid -f python3 {ROOT}/service.py --port 18085 >{ROOT}/service.log 2>&1 < /dev/null
  fi
  for i in $(seq 25); do curl -sf -m 1 http://127.0.0.1:18085/health >/dev/null && break; sleep 1; done
  curl -sf -m 2 http://127.0.0.1:18085/health >/dev/null
  setsid -f libreoffice --impress {deck} >{ROOT}/soffice.log 2>&1 < /dev/null
  sleep 3
  touch /tmp/conc03-runtime/ready
else
  if ! curl -sf -m 1 http://127.0.0.1:18085/health >/dev/null; then
    setsid -f python3 {ROOT}/service.py --port 18085 >{ROOT}/service.log 2>&1 < /dev/null
    sleep 2
  fi
fi""")
    if open_chrome:
        C.sh(sc, "pkill -x chrome >/dev/null 2>&1 || true; pkill -x socat >/dev/null 2>&1 || true")
        sc.launch("exec google-chrome --remote-debugging-port=1337 --force-device-scale-factor=1", shell=True)
        C.open_chrome(sc, [URL])


def _fetch(env, dest: Path, paths: list[tuple[str, str]]):
    dest.mkdir(parents=True, exist_ok=True)
    for guest, name in paths:
        try:
            C.fetch(env, guest, str(dest / name))
        except Exception:
            # Missing outputs after an agent error score as absent evidence;
            # they must not mask the underlying run status.
            continue


def _evaluate(env, actor):
    base = Path(os.environ.get("CONC03_EVAL_OUT", tempfile.mkdtemp(prefix="conc03-eval-")))
    out = base / f"actor-{actor}"
    out.mkdir(parents=True, exist_ok=True)
    workspace = out / "workspace"
    if actor == "a":
        _fetch(env, workspace, [("/home/user/workspace/out_a/approval_summary.csv", "approval_summary.csv")])
    else:
        _fetch(env, workspace, [("/home/user/workspace/out_b/Safety_Brief.pptx", "Safety_Brief.pptx"),
                                ("/home/user/workspace/out_b/Safety_Brief.pdf", "Safety_Brief.pdf")])
    state_path = out / "state.json"
    try:
        C.fetch(env, STATE, str(state_path))
    except Exception:
        pass
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    asset_root = Path(os.environ.get("PARAGUI_TASK_ASSETS") or Path.cwd()) / "CONC-03" / "guest"
    result = grade(workspace, state, asset_root, out / "rendered")
    (out / "checks.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    key = "actor_a" if actor == "a" else "actor_b"
    return C.result(result[key], {"checks": result["checks"][key], "flags": result["flags"],
                                  "popover_dismiss_count": state.get("popover_dismiss_count", 0)})


def evaluate_actor_a(env):
    return _evaluate(env, "a")


def evaluate_actor_b(env):
    return _evaluate(env, "b")
