"""Passive window-focus and small-file version recorder, running in the task VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = args.directory
    root.mkdir(parents=True, exist_ok=True)
    watched = json.loads((root / "watch.json").read_text())
    (root / "files").mkdir(exist_ok=True)
    output = (root / "events.jsonl").open("a", buffering=1)
    def emit(**event):
        output.write(json.dumps({"ts": time.time(), **event}) + "\n")
    display = None
    try:
        from Xlib import display as xdisplay
        display = xdisplay.Display(os.environ.get("DISPLAY", ":0"))
        window_root = display.screen().root
        active_atom = display.intern_atom("_NET_ACTIVE_WINDOW")
        name_atom = display.intern_atom("_NET_WM_NAME")
    except Exception as error:
        emit(kind="observer_error", component="focus", error=type(error).__name__ + ": " + str(error))
    previous_window, previous_files, versions = None, {}, {}
    emit(kind="started", watch_files=watched)
    while not (root / "STOP").exists():
        if display is not None:
            try:
                prop = window_root.get_full_property(active_atom, 0)
                window_id = int(prop.value[0]) if prop is not None and len(prop.value) else 0
                window = display.create_resource_object("window", window_id) if window_id else None
                title = window.get_full_property(name_atom, 0) if window else None
                value = title.value if title is not None else ""
                if isinstance(value, bytes):
                    value = value.decode(errors="replace")
                state = (window_id, str(value), tuple(window.get_wm_class() or ()) if window else ())
                if state != previous_window:
                    emit(kind="focus", window=window_id, title=state[1], app=state[2])
                    previous_window = state
            except Exception:
                pass
        for index, item in enumerate(watched):
            path = Path(item)
            try:
                stat = path.stat()
                identity = (stat.st_mtime_ns, stat.st_size)
                if previous_files.get(item) == identity:
                    continue
                previous_files[item] = identity
                data = path.read_bytes() if stat.st_size <= 2 * 1024 * 1024 else None
                version = versions.get(item, 0) + 1
                versions[item] = version
                snapshot = None
                if data is not None and version <= 200:
                    snapshot = f"files/{index:02d}-{version:04d}-{path.name}"
                    (root / snapshot).write_bytes(data)
                emit(kind="file", path=item, size=stat.st_size, version=version, snapshot=snapshot,
                     sha256=hashlib.sha256(data).hexdigest() if data is not None else None)
            except FileNotFoundError:
                if previous_files.get(item) != "missing":
                    emit(kind="file_missing", path=item)
                    previous_files[item] = "missing"
            except OSError as error:
                emit(kind="observer_error", component="file", path=item, error=type(error).__name__)
        time.sleep(0.5)
    emit(kind="stopped", versions=versions)
    output.close()
    if display is not None:
        display.close()


if __name__ == "__main__":
    main()
