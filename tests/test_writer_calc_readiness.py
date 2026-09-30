from pathlib import Path

import pytest

from scripts.run_writer_calc_v1 import (
    SetupReadinessError,
    _document_is_read_only,
    _document_title_matches,
    flat_calc,
    flat_writer,
    seed_shared_backend,
)


def test_document_title_read_only_gate():
    assert _document_title_matches(
        "document.fodt - LibreOffice Writer", "writer",
        "/tmp/swcub_office/document.fodt")
    assert _document_is_read_only(
        "document.fodt (read-only) - LibreOffice Writer")
    assert not _document_is_read_only("document.fodt - LibreOffice Writer")


def test_shared_backend_is_seeded_as_exact_writable_initial_files(tmp_path: Path):
    backend = tmp_path / "workspace-backend-task"
    backend.mkdir()
    manifest = seed_shared_backend(backend)

    assert (backend / "document.fodt").read_bytes() == flat_writer()
    assert (backend / "table.fods").read_bytes() == flat_calc()
    assert all(path.stat().st_mode & 0o777 == 0o666 for path in backend.iterdir())
    assert set(manifest) == {"document.fodt", "table.fods"}
    with pytest.raises(SetupReadinessError, match="not empty"):
        seed_shared_backend(backend)
