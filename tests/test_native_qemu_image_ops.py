from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from oscombo import qemu_image_ops


def test_base_inspection_uses_force_share_for_live_guest_backing(tmp_path, monkeypatch):
    base = tmp_path / "base.qcow2"
    base.touch()
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"format":"qcow2","virtual-size":1073741824}', stderr="")

    monkeypatch.setattr(qemu_image_ops.subprocess, "run", fake_run)
    assert qemu_image_ops.inspect_base_image("qemu-img", base, {}) == {"format": "qcow2", "virtual-size": 1073741824}
    assert calls[0][0] == ["qemu-img", "info", "-U", "--output=json", str(base)]


def test_base_inspection_rejects_non_qcow_image(tmp_path, monkeypatch):
    base = tmp_path / "base.raw"
    base.touch()
    monkeypatch.setattr(qemu_image_ops.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=0, stdout='{"format":"raw"}', stderr=""))
    with pytest.raises(RuntimeError, match="expected a qcow2"):
        qemu_image_ops.inspect_base_image("qemu-img", base, {})


def test_overlay_creation_does_not_reopen_shared_base(tmp_path, monkeypatch):
    base, overlay = tmp_path / "base.qcow2", tmp_path / "overlay.qcow2"
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(qemu_image_ops.subprocess, "run", fake_run)
    qemu_image_ops.create_guest_overlay("qemu-img", base, overlay, 1073741824, {})
    assert calls[0][0] == ["qemu-img", "create", "-u", "-q", "-f", "qcow2",
                            "-F", "qcow2", "-b", str(base), str(overlay), "1073741824"]


def test_shared_readonly_backing_uses_explicit_blockdev_graph(tmp_path):
    import json

    base, overlay = tmp_path / "base.qcow2", tmp_path / "guest.qcow2"
    args = qemu_image_ops.readonly_backed_disk_args(base, overlay)
    blockdevs = [json.loads(args[index + 1]) for index, value in enumerate(args[:-1])
                 if value == "-blockdev"]
    assert len(blockdevs) == 4
    assert blockdevs[0] == {"driver": "file", "filename": str(overlay),
                            "node-name": "guest-overlay-file"}
    assert blockdevs[1] == {"driver": "file", "filename": str(base),
                            "node-name": "shared-base-file", "locking": "off",
                            "read-only": True}
    assert blockdevs[2] == {"driver": "qcow2", "file": "shared-base-file",
                            "node-name": "shared-base-format", "read-only": True}
    assert blockdevs[3] == {"driver": "qcow2", "file": "guest-overlay-file",
                            "node-name": "guest-disk", "backing": "shared-base-format"}
    assert args[-2:] == ["-device", "ide-hd,drive=guest-disk,bus=ide.0,unit=0"]
