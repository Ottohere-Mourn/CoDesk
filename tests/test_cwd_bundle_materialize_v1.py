from scripts import probe_cwd_bundle_v2_scripted as controls
from swcub.tasks.cwd_bundle_oracle_v1 import evaluate_cwd_bundle_state


def test_materialize_empty_state_produces_a_scoreable_root(tmp_path, monkeypatch):
    monkeypatch.setattr(controls, "_read_guest_file", lambda _desktop, _path: None)
    root, state, archive, archive_path = controls._materialize_state(
        tmp_path, "empty", object(), object())
    assert root.is_dir()
    assert state["work/a/deliverables/release-note.txt"]["present"] is False
    assert archive is None
    assert archive_path is None
    result = evaluate_cwd_bundle_state(
        str(root), expected_a=b"A", expected_b=b"B")
    assert result["task_success"] is False


def test_materialize_state_uses_explicit_guest_root(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(controls, "_read_guest_file",
                        lambda _desktop, path: (seen.append(path), None)[1])
    controls._materialize_state(
        tmp_path, "custom-root", object(), object(), guest_root="/tmp/codesk-custom")
    assert seen
    assert all(path.startswith("/tmp/codesk-custom/") for path in seen)
