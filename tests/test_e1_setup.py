from types import SimpleNamespace
import evaluation_examples.task_class.pg_e1 as pair

class _Response:
    def __init__(self, ready):
        self.ready = ready
    def raise_for_status(self):
        pass
    def json(self):
        return {"output": "E1_READY\n" if self.ready else ""}

def test_shared_pair_setup_opens_and_uploads_only_once(monkeypatch):
    state = {"ready": False}
    uploads, opens, marks = [], [], []
    monkeypatch.setattr(pair.requests, "post", lambda *a, **k: _Response(state["ready"]))
    monkeypatch.setattr(pair, "upload", lambda sc, files: uploads.append(files))
    def opened(path):
        opens.append(path)
    def sh(sc, command):
        marks.append(command)
        state["ready"] = True
    monkeypatch.setattr(pair, "sh", sh)
    sc = SimpleNamespace(vm_ip="127.0.0.1", server_port=5000, _open_setup=lambda p: opened(p))
    pair.setup(sc)
    pair.setup(sc)
    assert len(uploads) == len(opens) == len(marks) == 1
