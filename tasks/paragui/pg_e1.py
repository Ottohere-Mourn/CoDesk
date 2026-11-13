"""EDIT-MODE1 setup/evaluation: two legitimate Writer edits in one saved release note."""
import requests
from evaluation_examples.task_class.pg_common import HOME, sh, upload

DOC = f"{HOME}/Documents/Operations/Release-review.odt"
MARKER = f"{HOME}/.codesk-edit-mode1-pair-setup-v1"

def _already_open(sc):
    response = requests.post(
        f"http://{sc.vm_ip}:{sc.server_port}/execute",
        json={"command": ["bash", "-lc", f"test -f {MARKER} && echo E1_READY"],
              "shell": False, "timeout": 20},
        timeout=25,
    )
    response.raise_for_status()
    return "E1_READY" in (response.json().get("output") or "")

def setup(sc):
    # The dual-task runner invokes pair setup once for each task in a Shared Guest.
    # Upload/open exactly once; a second open causes LO's external-file-changed dialog.
    if _already_open(sc):
        return
    upload(sc, [("e1/Release-review.odt", DOC)])
    sc._open_setup(DOC)
    sh(sc, f"touch {MARKER}")

def evaluate_insert(env, dest):
    from evaluation_examples.task_class.pg_e1_oracle import evaluate_insert as f
    return f(env, dest)

def evaluate_code(env, dest):
    from evaluation_examples.task_class.pg_e1_oracle import evaluate_code as f
    return f(env, dest)
