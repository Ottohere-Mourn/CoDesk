"""Create a versioned, isolated OSCombo runner copy with unlimited-step support.

The original FoodRecall checkout is deliberately left untouched.  This helper
copies only the runner and ParaGUI task builder tree into a fresh RAID-backed
directory, then changes the copied StepLoopHarness so ``--max-steps 0`` means
unlimited steps.  The per-role wall-clock timeout remains in force.
"""
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


def _ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in {"__pycache__", ".pytest_cache"} or name.endswith(".pyc")}


def _copy_tree_plain(source: Path, destination: Path) -> None:
    """Copy file bytes without chmod/utime/xattr operations (RAID may deny setstat)."""
    for current, dirs, files in os.walk(source):
        here = Path(current)
        rel = here.relative_to(source)
        dirs[:] = [name for name in dirs if name not in {"__pycache__", ".pytest_cache"}]
        target_dir = destination / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        ignored = _ignore(str(here), dirs + files)
        for name in files:
            if name in ignored:
                continue
            src = here / name
            dst = target_dir / name
            if src.is_symlink():
                continue
            shutil.copyfile(src, dst)


def patch_unlimited_step_loop(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    old_head = "        for step in range(1, ctx.max_steps + 1):\n            if ctx.stop.is_set() or time.time() - started_at > self.wall_s:\n"
    new_head = (
        "        # A positive max_steps is a cap; zero is unlimited for this approved batch.\n"
        "        step = 1\n"
        "        while True:\n"
        "            if ctx.max_steps > 0 and step > ctx.max_steps:\n"
        "                res.status = \"max_steps\"\n"
        "                return res\n"
        "            if ctx.stop.is_set() or time.time() - started_at > self.wall_s:\n"
    )
    old_tail = "            time.sleep(self.step_pause)\n        res.status = \"max_steps\"\n        return res\n"
    new_tail = "            time.sleep(self.step_pause)\n            step += 1\n"
    if source.count(old_head) != 1 or source.count(old_tail) != 1:
        raise RuntimeError("unexpected upstream StepLoopHarness structure; refusing to patch")
    source = source.replace(old_head, new_head, 1).replace(old_tail, new_tail, 1)
    path.write_text(source, encoding="utf-8")


def prepare(source_repo: Path, destination: Path) -> Path:
    source_repo = source_repo.resolve()
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    _copy_tree_plain(source_repo / "oscombo", destination / "oscombo")
    _copy_tree_plain(source_repo / "tasks" / "paragui", destination / "tasks" / "paragui")
    patch_unlimited_step_loop(destination / "oscombo" / "harness" / "step_loop.py")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_repo", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(f"runner_overlay={prepare(args.source_repo, args.destination)}")
    print("unlimited_steps=enabled via --max-steps 0; wall_clock_timeout=unchanged")


if __name__ == "__main__":
    main()
