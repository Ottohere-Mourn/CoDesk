import threading
import time

from oscombo.desktop_tools import _shared_action_lock


def test_shared_action_lock_serializes_mutation_critical_sections(tmp_path, monkeypatch):
    lock = tmp_path / "shared.lock"
    import oscombo.desktop_tools as tools
    monkeypatch.setattr(tools, "ACTION_LOCK_PATH", str(lock))
    events = []
    barrier = threading.Barrier(2)

    def worker(name):
        barrier.wait()
        with tools._shared_action_lock():
            entered = time.perf_counter()
            events.append((name, "in", entered))
            time.sleep(0.12)
            events.append((name, "out", time.perf_counter()))

    threads = [threading.Thread(target=worker, args=(x,)) for x in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    spans = {name: (next(t for n, edge, t in events if n == name and edge == "in"),
                    next(t for n, edge, t in events if n == name and edge == "out"))
             for name in ("A", "B")}
    assert spans["A"][1] <= spans["B"][0] or spans["B"][1] <= spans["A"][0]
