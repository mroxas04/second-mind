"""Tests for the journal ingestion inspection CLI."""

from pathlib import Path
import subprocess
import sys

import pytest


def write_journal(path: Path, content: str) -> Path:
    """Write a synthetic CLI fixture and return its path."""

    path.write_text(content, encoding="utf-8", newline="")
    return path


def run_cli(path: Path) -> subprocess.CompletedProcess[str]:
    """Run the module CLI in the active test environment."""

    return subprocess.run(
        [sys.executable, "-m", "second_mind.ingest", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_cli_prints_a_summary_for_each_valid_entry(tmp_path: Path) -> None:
    body = "A short body.\n"
    write_journal(tmp_path / "2026-07-20-cli-check.md", f"# CLI check\n{body}")

    result = run_cli(tmp_path)

    assert result.returncode == 0
    assert result.stdout == (
        "date=2026-07-20 | title=CLI check | "
        "source=2026-07-20-cli-check.md | "
        f"body_chars={len(body)}\n"
    )
    assert result.stderr == ""


def test_cli_prints_entries_in_chronological_order(tmp_path: Path) -> None:
    write_journal(tmp_path / "2026-07-20-latest.md", "Latest.\n")
    write_journal(tmp_path / "2025-12-31-earliest.md", "Earliest.\n")
    write_journal(tmp_path / "2026-01-15-middle.md", "Middle.\n")

    result = run_cli(tmp_path)

    assert result.returncode == 0
    assert [line.split(" | ", 1)[0] for line in result.stdout.splitlines()] == [
        "date=2025-12-31",
        "date=2026-01-15",
        "date=2026-07-20",
    ]


@pytest.mark.parametrize("path_kind", ["missing", "file"])
def test_cli_rejects_an_invalid_directory(
    tmp_path: Path,
    path_kind: str,
) -> None:
    path = tmp_path / path_kind
    if path_kind == "file":
        path.write_text("not a directory", encoding="utf-8")

    result = run_cli(path)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "Journal directory does not exist or is not a directory" in result.stderr
    assert str(path) in result.stderr


def test_cli_rejects_an_empty_directory(tmp_path: Path) -> None:
    result = run_cli(tmp_path)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "no valid journal entries found" in result.stderr


def test_cli_keeps_valid_output_and_warnings_on_separate_streams(
    tmp_path: Path,
) -> None:
    valid = write_journal(tmp_path / "2026-07-20-valid.md", "Valid body.\n")
    invalid = write_journal(tmp_path / "invalid-name.md", "Invalid filename.\n")

    result = run_cli(tmp_path)

    assert result.returncode == 0
    assert f"source={valid.name}" in result.stdout
    assert invalid.name not in result.stdout
    assert "UserWarning: Skipping Invalid journal" in result.stderr
    assert str(invalid) in result.stderr
    assert "filename must match" in result.stderr
