"""Tests for local backup snapshot creation and verification."""

from pathlib import Path
import sqlite3

import pytest

from second_mind.backup import create_backup, restore_backup, verify_backup


def write_backup_inputs(tmp_path: Path) -> tuple[Path, Path]:
    """Create fictional journals and a synthetic local index for backup tests."""

    journals = tmp_path / "journals"
    journals.mkdir()
    (journals / "2026-12-02-library.md").write_text(
        "# Fictional library\nA paper crane marked the reserved shelf.\n",
        encoding="utf-8",
    )
    nested = journals / "archive"
    nested.mkdir()
    (nested / "2026-12-03-garden.md").write_text(
        "# Fictional garden\nBlue flags marked the winter beds.\n",
        encoding="utf-8",
    )
    index_path = tmp_path / "indexes" / "journals.sqlite3"
    index_path.parent.mkdir()
    with sqlite3.connect(index_path) as connection:
        connection.execute("CREATE TABLE chunks (text TEXT NOT NULL)")
        connection.execute("INSERT INTO chunks VALUES (?)", ("fictional index",))
    return journals, index_path


def test_create_backup_copies_and_verifies_local_snapshot(tmp_path: Path) -> None:
    journals, index_path = write_backup_inputs(tmp_path)

    summary = create_backup(
        journals,
        tmp_path / "backups",
        index_path,
        snapshot_name="fictional-snapshot",
    )
    verification = verify_backup(summary.snapshot_path)

    assert summary.files == 3
    assert summary.bytes_copied > 0
    assert (summary.snapshot_path / "manifest.json").is_file()
    assert (summary.snapshot_path / "journals/2026-12-02-library.md").is_file()
    assert (
        summary.snapshot_path / "journals/archive/2026-12-03-garden.md"
    ).is_file()
    assert (summary.snapshot_path / "index/journals.sqlite3").is_file()
    with sqlite3.connect(
        summary.snapshot_path / "index/journals.sqlite3"
    ) as connection:
        assert connection.execute("SELECT text FROM chunks").fetchone() == (
            "fictional index",
        )
    assert verification.valid
    assert verification.files == 3
    assert verification.bytes_checked == summary.bytes_copied


def test_verify_backup_detects_changed_file(tmp_path: Path) -> None:
    journals, index_path = write_backup_inputs(tmp_path)
    summary = create_backup(
        journals,
        tmp_path / "backups",
        index_path,
        snapshot_name="fictional-snapshot",
    )
    stored_journal = summary.snapshot_path / "journals/2026-12-02-library.md"
    stored_journal.write_text("changed fictional content\n", encoding="utf-8")

    verification = verify_backup(summary.snapshot_path)

    assert not verification.valid
    assert verification.errors == (
        "size mismatch: journals/2026-12-02-library.md",
    )


def test_restore_backup_recreates_verified_snapshot(tmp_path: Path) -> None:
    journals, index_path = write_backup_inputs(tmp_path)
    summary = create_backup(journals, tmp_path / "backups", index_path, snapshot_name="snapshot")
    restored = restore_backup(summary.snapshot_path, tmp_path / "restored")
    assert restored.files == 3
    assert (restored.restore_path / "journals/2026-12-02-library.md").read_text(encoding="utf-8").startswith("# Fictional")
    assert verify_backup(restored.restore_path).valid


def test_create_backup_never_overwrites_snapshot(tmp_path: Path) -> None:
    journals, index_path = write_backup_inputs(tmp_path)
    destination = tmp_path / "backups"
    create_backup(
        journals,
        destination,
        index_path,
        snapshot_name="fictional-snapshot",
    )

    with pytest.raises(FileExistsError, match="already exists"):
        create_backup(
            journals,
            destination,
            index_path,
            snapshot_name="fictional-snapshot",
        )


def test_create_backup_rejects_destination_inside_journals(tmp_path: Path) -> None:
    journals, index_path = write_backup_inputs(tmp_path)

    with pytest.raises(ValueError, match="must not be inside"):
        create_backup(journals, journals / "backups", index_path)


def test_create_backup_requires_existing_index(tmp_path: Path) -> None:
    journals, _ = write_backup_inputs(tmp_path)

    with pytest.raises(ValueError, match="index does not exist"):
        create_backup(journals, tmp_path / "backups", tmp_path / "missing.sqlite3")


def test_verify_backup_rejects_manifest_path_traversal(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "manifest.json").write_text(
        '{"version": 1, "files": [{"path": "../outside", '
        '"role": "journal", "sha256": "' + "0" * 64 + '", "size": 0}]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid file record"):
        verify_backup(snapshot)
