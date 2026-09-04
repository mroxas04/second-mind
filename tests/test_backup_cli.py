"""End-to-end tests for the local backup command."""

from pathlib import Path
import sqlite3
import subprocess
import sys


def run_backup(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the backup module in the active test environment."""

    return subprocess.run(
        [sys.executable, "-m", "second_mind.backup", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def write_cli_inputs(tmp_path: Path) -> tuple[Path, Path]:
    """Write fictional local data for a backup CLI test."""

    journals = tmp_path / "journals"
    journals.mkdir()
    (journals / "2026-12-04-station.md").write_text(
        "# Fictional station\nA brass clock hung above platform seven.\n",
        encoding="utf-8",
    )
    index_path = tmp_path / "journals.sqlite3"
    with sqlite3.connect(index_path) as connection:
        connection.execute("CREATE TABLE chunks (text TEXT NOT NULL)")
        connection.execute("INSERT INTO chunks VALUES (?)", ("fictional index",))
    return journals, index_path


def test_cli_creates_then_verifies_snapshot(tmp_path: Path) -> None:
    journals, index_path = write_cli_inputs(tmp_path)
    backup_root = tmp_path / "backups"
    snapshot = backup_root / "fictional-snapshot"

    created = run_backup(
        "create",
        str(journals),
        str(backup_root),
        "--index",
        str(index_path),
        "--name",
        snapshot.name,
    )
    verified = run_backup("verify", str(snapshot))

    assert created.returncode == 0
    assert created.stderr == ""
    assert f"snapshot={snapshot}" in created.stdout
    assert "files=2" in created.stdout
    assert "verified=yes" in created.stdout
    assert verified.returncode == 0
    assert verified.stderr == ""
    assert f"snapshot={snapshot}" in verified.stdout
    assert "files=2" in verified.stdout
    assert "verified=yes" in verified.stdout

    restored = run_backup("restore", str(snapshot), str(tmp_path / "restored"))
    assert restored.returncode == 0
    assert restored.stderr == ""
    assert "files=2" in restored.stdout
    assert "verified=yes" in restored.stdout
    assert (tmp_path / "restored/manifest.json").is_file()


def test_cli_reports_invalid_snapshot(tmp_path: Path) -> None:
    result = run_backup("verify", str(tmp_path / "missing"))

    assert result.returncode == 1
    assert result.stdout == ""
    assert "backup snapshot does not exist" in result.stderr


def test_cli_reports_invalid_index_database(tmp_path: Path) -> None:
    journals, index_path = write_cli_inputs(tmp_path)
    index_path.write_bytes(b"not a sqlite database")

    result = run_backup(
        "create",
        str(journals),
        str(tmp_path / "backups"),
        "--index",
        str(index_path),
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "not a database" in result.stderr
