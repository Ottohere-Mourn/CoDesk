from __future__ import annotations
import io
import tarfile

from swcub.tasks.cwd_bundle_oracle_v1 import evaluate_tar_exact_files


def make_tar(path, entries):
    with tarfile.open(path, "w:gz") as archive:
        for name, payload, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == "dir":
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                archive.addfile(info)
            else:
                info.size = len(payload)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(payload))


def test_exact_clean_bundle_passes(tmp_path):
    archive = tmp_path / "clean.tar.gz"
    make_tar(archive, [
        ("deliverables", b"", "dir"),
        ("deliverables/check.txt", b"CHECK-OK-1", "file"),
    ])
    result = evaluate_tar_exact_files(str(archive), {"deliverables/check.txt": b"CHECK-OK-1"})
    assert result["pass"] is True
    assert result["observed_files"] == ["deliverables/check.txt"]


def test_foreign_release_file_contamination_fails(tmp_path):
    archive = tmp_path / "polluted.tar.gz"
    make_tar(archive, [
        ("deliverables", b"", "dir"),
        ("deliverables/check.txt", b"CHECK-OK-1", "file"),
        ("deliverables/release-note.txt", b"RELEASE-OK-1", "file"),
    ])
    result = evaluate_tar_exact_files(str(archive), {"deliverables/check.txt": b"CHECK-OK-1"})
    assert result["pass"] is False
    assert "deliverables/release-note.txt" in result["unexpected_files"]
    assert "unexpected_file:deliverables/release-note.txt" in result["issues"]


def test_parent_traversal_member_fails_without_extraction(tmp_path):
    archive = tmp_path / "traversal.tar.gz"
    make_tar(archive, [
        ("deliverables/check.txt", b"CHECK-OK-1", "file"),
        ("../outside.txt", b"not extracted", "file"),
    ])
    result = evaluate_tar_exact_files(str(archive), {"deliverables/check.txt": b"CHECK-OK-1"})
    assert result["pass"] is False
    assert any(issue.startswith("path_traversal:") for issue in result["issues"])


def test_duplicate_member_fails(tmp_path):
    archive = tmp_path / "duplicate.tar.gz"
    make_tar(archive, [
        ("deliverables/check.txt", b"CHECK-OK-1", "file"),
        ("deliverables/check.txt", b"CHECK-OK-1", "file"),
    ])
    result = evaluate_tar_exact_files(str(archive), {"deliverables/check.txt": b"CHECK-OK-1"})
    assert result["pass"] is False
    assert "duplicate_member:deliverables/check.txt" in result["issues"]


def test_wrong_content_fails(tmp_path):
    archive = tmp_path / "wrong-content.tar.gz"
    make_tar(archive, [("deliverables/check.txt", b"OTHER", "file")])
    result = evaluate_tar_exact_files(str(archive), {"deliverables/check.txt": b"CHECK-OK-1"})
    assert result["pass"] is False
    assert "content_mismatch:deliverables/check.txt" in result["issues"]


def test_unsafe_expected_path_rejected():
    import pytest
    with pytest.raises(ValueError):
        evaluate_tar_exact_files("unused.tar", {"../check.txt": b"CHECK"})

def test_symlink_member_is_rejected(tmp_path):
    archive = tmp_path / "symlink.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        link = tarfile.TarInfo("deliverables/check.txt")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside.txt"
        tar.addfile(link)
    result = evaluate_tar_exact_files(str(archive), {"deliverables/check.txt": b"CHECK-OK-1"})
    assert result["pass"] is False
    assert "non_regular_member:deliverables/check.txt" in result["issues"]


def add_tar(path, entries):
    with tarfile.open(path, "w:gz") as archive:
        for name, payload, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == "dir":
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            else:
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))


def seed_bundle_root(root, *, a_expected, a_in_b, archive_has_a):
    from pathlib import Path
    from swcub.tasks.cwd_bundle_oracle_v1 import B_ARCHIVE_PATH
    root = Path(root)
    a_path = root / "work/a/deliverables/release-note.txt"
    b_path = root / "work/b/deliverables/check.txt"
    wrong_path = root / "work/b/deliverables/release-note.txt"
    archive_path = root / B_ARCHIVE_PATH
    for path in (a_path, b_path, wrong_path, archive_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    if a_expected:
        a_path.write_bytes(b"RELEASE-OK-1")
    b_path.write_bytes(b"CHECK-OK-1")
    if a_in_b:
        wrong_path.write_bytes(b"RELEASE-OK-1")
    entries = [
        ("deliverables", b"", "dir"),
        ("deliverables/check.txt", b"CHECK-OK-1", "file"),
    ]
    if archive_has_a:
        entries.append(("deliverables/release-note.txt", b"RELEASE-OK-1", "file"))
    add_tar(archive_path, entries)


def test_isolated_bundle_state_passes(tmp_path):
    from swcub.tasks.cwd_bundle_oracle_v1 import evaluate_cwd_bundle_state
    seed_bundle_root(tmp_path, a_expected=True, a_in_b=False, archive_has_a=False)
    result = evaluate_cwd_bundle_state(
        str(tmp_path), expected_a=b"RELEASE-OK-1", expected_b=b"CHECK-OK-1")
    assert result["task_success"] is True
    assert result["a_payload_at_b_wrong_path"] is False
    assert result["b_archive_exact"] is True


def test_shared_pollution_fails_durable_bundle(tmp_path):
    from swcub.tasks.cwd_bundle_oracle_v1 import evaluate_cwd_bundle_state
    seed_bundle_root(tmp_path, a_expected=False, a_in_b=True, archive_has_a=True)
    result = evaluate_cwd_bundle_state(
        str(tmp_path), expected_a=b"RELEASE-OK-1", expected_b=b"CHECK-OK-1")
    assert result["task_success"] is False
    assert result["a_payload_at_b_wrong_path"] is True
    assert result["b_archive_exact"] is False
    assert "deliverables/release-note.txt" in result["b_archive"]["unexpected_files"]


def test_a_recovery_cannot_repair_already_polluted_bundle(tmp_path):
    from swcub.tasks.cwd_bundle_oracle_v1 import evaluate_cwd_bundle_state
    seed_bundle_root(tmp_path, a_expected=True, a_in_b=True, archive_has_a=True)
    result = evaluate_cwd_bundle_state(
        str(tmp_path), expected_a=b"RELEASE-OK-1", expected_b=b"CHECK-OK-1")
    assert result["a_expected_path_exact"] is True
    assert result["b_expected_path_exact"] is True
    assert result["b_archive_exact"] is False
    assert result["task_success"] is False


def test_symlinked_expected_path_is_not_followed(tmp_path):
    from pathlib import Path
    from swcub.tasks.cwd_bundle_oracle_v1 import evaluate_cwd_bundle_state
    seed_bundle_root(tmp_path, a_expected=True, a_in_b=False, archive_has_a=False)
    a_path = Path(tmp_path) / "work/a/deliverables/release-note.txt"
    a_path.unlink()
    a_path.symlink_to(Path(tmp_path) / "work/b/deliverables/check.txt")
    result = evaluate_cwd_bundle_state(
        str(tmp_path), expected_a=b"RELEASE-OK-1", expected_b=b"CHECK-OK-1")
    assert result["task_success"] is False
    assert result["a_expected_path_read_error"] == "symlink_path"

def test_first_bundle_snapshot_and_final_rebuild_are_separate_endpoints(tmp_path):
    from pathlib import Path
    from shutil import copyfile
    from swcub.tasks.cwd_bundle_oracle_v1 import B_ARCHIVE_PATH, A_WRONG_PATH, evaluate_cwd_bundle_state
    root = tmp_path / "workspace"
    seed_bundle_root(root, a_expected=False, a_in_b=True, archive_has_a=True)
    # Freeze the actual first-created bundle while A's release-note is in B's
    # worktree; keep its byte-for-byte snapshot untouched during recovery.
    first_created = tmp_path / "first-created.tar.gz"
    copyfile(Path(root) / B_ARCHIVE_PATH, first_created)
    at_creation = evaluate_cwd_bundle_state(
        str(root), expected_a=b"RELEASE-OK-1", expected_b=b"CHECK-OK-1",
        archive_path=str(first_created))
    assert at_creation["a_expected_path_exact"] is False
    assert at_creation["a_payload_at_b_wrong_path"] is True
    assert at_creation["b_archive_exact"] is False
    assert at_creation["task_success"] is False

    # Legitimate recovery restores A's file, removes the misplaced copy, and
    # rebuilds B's archive from B's own declared check deliverable.
    a_path = Path(root) / "work/a/deliverables/release-note.txt"
    wrong_path = Path(root) / A_WRONG_PATH
    a_path.parent.mkdir(parents=True, exist_ok=True)
    a_path.write_bytes(b"RELEASE-OK-1")
    wrong_path.unlink()
    clean_archive = Path(root) / B_ARCHIVE_PATH
    add_tar(clean_archive, [
        ("deliverables", b"", "dir"),
        ("deliverables/check.txt", b"CHECK-OK-1", "file"),
    ])
    final = evaluate_cwd_bundle_state(
        str(root), expected_a=b"RELEASE-OK-1", expected_b=b"CHECK-OK-1")
    assert final["a_expected_path_exact"] is True
    assert final["a_wrong_path_clean"] is True
    assert final["b_archive_exact"] is True
    assert final["task_success"] is True
    # Re-evaluating final files against the immutable first-created archive
    # retains the creation-time failure rather than hiding it after recovery.
    first_snapshot_at_final = evaluate_cwd_bundle_state(
        str(root), expected_a=b"RELEASE-OK-1", expected_b=b"CHECK-OK-1",
        archive_path=str(first_created))
    assert first_snapshot_at_final["b_archive_exact"] is False
    assert first_snapshot_at_final["task_success"] is False
    assert first_snapshot_at_final["b_archive_evaluation_path"] == str(first_created)


def test_misplaced_a_copy_is_out_of_spec_even_if_final_archive_is_clean(tmp_path):
    from swcub.tasks.cwd_bundle_oracle_v1 import evaluate_cwd_bundle_state
    seed_bundle_root(tmp_path, a_expected=True, a_in_b=True, archive_has_a=False)
    result = evaluate_cwd_bundle_state(
        str(tmp_path), expected_a=b"RELEASE-OK-1", expected_b=b"CHECK-OK-1")
    assert result["a_expected_path_exact"] is True
    assert result["a_wrong_path_clean"] is False
    assert result["a_payload_at_b_wrong_path"] is True
    assert result["b_archive_exact"] is True
    assert result["task_success"] is False
