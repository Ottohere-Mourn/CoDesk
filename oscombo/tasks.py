"""paraGUI task pairs (``tasks/paragui``): install them into the OSWorld checkout and build their assets.

  python -m oscombo tasks list                      # pairs and their two task specs (v2/pg<pair><name>)
  python -m oscombo tasks install [--pairs w1 m2]   # copy task classes + build assets (OSWorld venv python)

The task classes are OSWorld 2.0 style (``task_pg*.py`` + shared ``pg_*.py`` modules) and live in
``$OSWORLD_DIR/evaluation_examples/task_class/`` once installed; run them as ``v2/pg<pair><name>``. Their assets
(documents, seeded web-app databases, Thunderbird profiles, ``expected.json`` ground truth) are generated
deterministically by ``tasks/paragui/build_*.py`` into ``$PARAGUI_TASK_ASSETS`` (default
``~/.cache/oscombo/paragui/assets``), which the task setup uploads into the Guest and the checkers read on the host.
The mail pairs start from the public OSWorld blank Thunderbird profile, downloaded once to ``$PARAGUI_TB_BASE``.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

from .osworld import osworld_dir

SRC = Path(__file__).resolve().parents[1] / "tasks" / "paragui"
DEFAULT_ASSETS = os.path.expanduser("~/.cache/oscombo/paragui/assets")
DEFAULT_TB_BASE = os.path.expanduser("~/.cache/oscombo/paragui/base/thunderbird-profile.tar.gz")
TB_BASE_URL = ("https://huggingface.co/datasets/xlangai/ubuntu_osworld_file_cache/resolve/main/thunderbird/"
               "dd84e895-72fd-4023-a336-97689ded257c/thunderbird-profile.tar.gz")


def pairs() -> dict[str, list[str]]:
    """{pair: [task id, task id]} from the task class files."""
    out: dict[str, list[str]] = defaultdict(list)
    for f in sorted(SRC.glob("task_pg*.py")):
        m = re.match(r"task_(pg([a-z]\d)\w+)\.py", f.name)
        if m:
            out[m.group(2)].append(m.group(1))
    return dict(out)


def install(only: list[str] | None, assets: str, tb_base: str) -> None:
    dst = osworld_dir() / "evaluation_examples" / "task_class"
    n = 0
    for f in sorted(SRC.glob("*.py")):
        if f.name.startswith(("pg_", "task_pg")):
            shutil.copy2(f, dst / f.name)
            n += 1
    print(f"copied {n} task modules to {dst}")
    if not os.path.exists(tb_base):
        os.makedirs(os.path.dirname(tb_base), exist_ok=True)
        print(f"downloading the blank OSWorld Thunderbird profile to {tb_base}")
        urllib.request.urlretrieve(os.environ.get("PARAGUI_TB_BASE_URL", TB_BASE_URL), tb_base)
    os.makedirs(assets, exist_ok=True)
    env = {**os.environ, "PARAGUI_TB_BASE": tb_base, "PARAGUI_TASK_ASSETS": assets}
    subprocess.run([sys.executable, str(SRC / "build_assets.py"), assets, *(only or [])], cwd=SRC, env=env,
                   check=True)
    print(f"assets in {assets}\nbefore running these tasks: export PARAGUI_TASK_ASSETS={assets}")


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="oscombo tasks", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="pairs and their task specs")
    i = sub.add_parser("install", help="copy task classes into OSWORLD_DIR and build assets")
    i.add_argument("--pairs", nargs="*", help="only these pairs (default: all)")
    i.add_argument("--assets", default=os.environ.get("PARAGUI_TASK_ASSETS", DEFAULT_ASSETS))
    i.add_argument("--tb-base", default=os.environ.get("PARAGUI_TB_BASE", DEFAULT_TB_BASE))
    a = ap.parse_args(argv)
    if a.cmd == "list":
        for p, ids in pairs().items():
            print(p, *(f"v2/{t}" for t in ids))
        return 0
    install(a.pairs, os.path.abspath(a.assets), os.path.abspath(a.tb_base))
    return 0
