"""Locate the OSWorld checkout, load task specs and normalize scores.

The official OSWorld code is not vendored. Point ``OSWORLD_DIR`` at a checkout of
https://github.com/xlang-ai/OSWorld-V2 (tag ``osworld-v2.1``, see ``infra/setup_osworld.sh``) and call
``activate()`` before importing anything from ``desktop_env`` or ``mm_agents``.

Task specs:
  ``<domain>/<uuid>``   classic OSWorld example  (evaluation_examples/examples/<domain>/<uuid>.json)
  ``v2/<NNN>``          OSWorld 2.0 task class   (evaluation_examples/task_class/task_<NNN>.py)
  ``path/to/task.json`` or ``path/to/task_xxx.py``  any task file
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULT_PASSWORD = "osworld-public-evaluation"  # sudo password of the public OSWorld-V2 Ubuntu Guest


def osworld_dir() -> Path:
    path = os.environ.get("OSWORLD_DIR")
    if not path:
        raise RuntimeError("OSWORLD_DIR is not set (path to an OSWorld-V2 checkout, see infra/setup_osworld.sh)")
    return Path(path).expanduser().resolve()


def client_password() -> str:
    return os.environ.get("OSWORLD_CLIENT_PASSWORD", DEFAULT_PASSWORD)


def activate() -> Path:
    """Make ``desktop_env`` / ``mm_agents`` importable and chdir into the checkout.

    The official evaluators and getters use repo-relative paths, so the process must run from there.
    """
    root = osworld_dir()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.chdir(root)
    return root


def task_path(spec: str, root: Path | None = None) -> Path:
    if spec.endswith((".json", ".py")):
        return Path(spec).expanduser().resolve()
    root = root or osworld_dir()
    domain, uid = spec.split("/", 1)
    if domain == "v2":
        return root / "evaluation_examples" / "task_class" / f"task_{uid}.py"
    return root / "evaluation_examples" / "examples" / domain / f"{uid}.json"


def load_task(spec: str, root: Path | None = None) -> Any:
    """Return the task config: a dict for json examples, a task object for OSWorld 2.0 task classes."""
    path = task_path(spec, root)
    if path.suffix == ".py":
        from task_loader import load_task_from_file  # from the OSWorld checkout (activate() first)
        return load_task_from_file(str(path))
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def task_get(task: Any, key: str, default: Any = None) -> Any:
    """Field access that works for json dicts and OSWorld 2.0 task objects (same rule as DesktopEnv._task_get)."""
    if task is None:
        return default
    if hasattr(task, "get") and callable(task.get):
        try:
            return task.get(key, default)
        except TypeError:
            return task.get(key)
    return getattr(task, key, default)


def score_value(result: Any) -> float:
    """OSWorld 2.0 tasks return {"score": ...} (partial credit), classic examples a number."""
    return float(result.get("score", 0.0)) if isinstance(result, dict) else float(result)
