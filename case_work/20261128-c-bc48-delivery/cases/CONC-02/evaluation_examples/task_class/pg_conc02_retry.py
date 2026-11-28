"""One shared Impress process, two independent decks, and blind final grading."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from evaluation_examples.task_class import pg_common as C
from evaluation_examples.task_class.conc02_grade import grade
from evaluation_examples.task_class.conc02_grade import load_expected

ROOT = "/home/user/.cache/paragui/conc02/CONC-02"
FILES = [
    ("CONC-02/guest/in_a/finance_memo.txt", "/home/user/workspace/in_a/finance_memo.txt"),
    ("CONC-02/guest/in_a/brand_swatch_a.png", "/home/user/workspace/in_a/brand_swatch_a.png"),
    ("CONC-02/guest/in_a/chart_rev.png", "/home/user/workspace/in_a/chart_rev.png"),
    ("CONC-02/guest/in_a/chart_margin.png", "/home/user/workspace/in_a/chart_margin.png"),
    ("CONC-02/guest/in_b/launch_memo.txt", "/home/user/workspace/in_b/launch_memo.txt"),
    ("CONC-02/guest/in_b/brand_swatch_b.png", "/home/user/workspace/in_b/brand_swatch_b.png"),
    ("CONC-02/guest/in_b/prod_front.png", "/home/user/workspace/in_b/prod_front.png"),
    ("CONC-02/guest/in_b/prod_side.png", "/home/user/workspace/in_b/prod_side.png"),
    ("CONC-02/guest/out_a/Q4_Finance_Final.pptx", "/home/user/workspace/out_a/Q4_Finance_Final.pptx"),
    ("CONC-02/guest/out_b/Product_Launch_Final.pptx", "/home/user/workspace/out_b/Product_Launch_Final.pptx"),
]


def _asset_destination(source: str) -> str:
    """Translate a task-assets-relative source path to its Guest cache path."""
    prefix = "CONC-02/"
    if not source.startswith(prefix):
        raise ValueError(f"CONC-02 asset path must begin with {prefix!r}: {source}")
    return f"{ROOT}/{source[len(prefix):]}"


def _staged_uploads():
    return [(source, _asset_destination(source)) for source, _ in FILES]


def setup(sc):
    # Uploads are rooted at task-assets/CONC-02. Strip that asset-root prefix
    # before joining the cache root; otherwise the Guest receives
    # ROOT/CONC-02/guest/... while the copy step reads ROOT/guest/....
    C.upload(sc, _staged_uploads())
    a_path = "/home/user/workspace/out_a/Q4_Finance_Final.pptx"
    b_path = "/home/user/workspace/out_b/Product_Launch_Final.pptx"
    script = f"""set -e
mkdir -p /home/user/workspace/in_a /home/user/workspace/in_b /home/user/workspace/out_a /home/user/workspace/out_b /tmp/conc02-runtime
if [ ! -f /tmp/conc02-runtime/ready ]; then
  cp {ROOT}/guest/in_a/* /home/user/workspace/in_a/
  cp {ROOT}/guest/in_b/* /home/user/workspace/in_b/
  cp {ROOT}/guest/out_a/Q4_Finance_Final.pptx {a_path}
  cp {ROOT}/guest/out_b/Product_Launch_Final.pptx {b_path}
  test -s /home/user/workspace/in_a/finance_memo.txt
  test -s /home/user/workspace/in_a/brand_swatch_a.png
  test -s /home/user/workspace/in_a/chart_rev.png
  test -s /home/user/workspace/in_a/chart_margin.png
  test -s /home/user/workspace/in_b/launch_memo.txt
  test -s /home/user/workspace/in_b/brand_swatch_b.png
  test -s /home/user/workspace/in_b/prod_front.png
  test -s /home/user/workspace/in_b/prod_side.png
  test -s {a_path}
  test -s {b_path}
  setsid -f libreoffice --impress {a_path} {b_path} >/tmp/conc02-runtime/soffice-launch.log 2>&1 < /dev/null
  for i in $(seq 60); do
    a_lock=$(find /home/user/workspace/out_a -maxdepth 1 -name '.~lock.Q4_Finance_Final.pptx#' -print -quit)
    b_lock=$(find /home/user/workspace/out_b -maxdepth 1 -name '.~lock.Product_Launch_Final.pptx#' -print -quit)
    if [ -n "$a_lock" ] && [ -n "$b_lock" ]; then break; fi
    sleep 1
  done
  test -n "$a_lock" && test -n "$b_lock"
  pgrep -x soffice.bin >/dev/null
  touch /tmp/conc02-runtime/ready
fi"""
    # SetupController.execute defaults to check=False. Make the required-file
    # checks a real setup gate so a bad Guest mapping cannot silently proceed.
    sc.execute(["bash", "-c", script], timeout=120, check=True)


def _evaluate(env, role):
    base = Path(os.environ.get("CONC02_EVAL_OUT", tempfile.mkdtemp(prefix="conc02-eval-")))
    out = base / f"actor-{role}"
    out.mkdir(parents=True, exist_ok=True)
    pptx_name = "Q4_Finance_Final.pptx" if role == "a" else "Product_Launch_Final.pptx"
    pdf_name = "Q4_Finance_Final.pdf" if role == "a" else "Product_Launch_Final.pdf"
    pptx_dest, pdf_dest = out / pptx_name, out / pdf_name
    # A timed-out/failed actor should still produce a deterministic zero score,
    # not fail the entire shared run while trying to fetch absent artifacts.
    for guest_path, local_path in ((f"/home/user/workspace/out_{role}/{pptx_name}", pptx_dest),
                                   (f"/home/user/workspace/out_{role}/{pdf_name}", pdf_dest)):
        try:
            C.fetch(env, guest_path, str(local_path))
        except Exception:
            pass
    result = grade(pptx_dest, pdf_dest, role, load_expected(), out / "rendered")
    (out / "checks.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return C.result(result["score"], {"flags": result["flags"], "checks": result["checks"], "render_dir": result.get("render_dir")})


def evaluate_actor_a(env):
    return _evaluate(env, "a")


def evaluate_actor_b(env):
    return _evaluate(env, "b")
