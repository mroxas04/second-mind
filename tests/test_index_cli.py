"""End-to-end tests for the local indexing and query CLI."""

from pathlib import Path
import subprocess
import sys


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the indexing module in the active test environment."""

    return subprocess.run(
        [sys.executable, "-m", "second_mind.index", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def test_cli_indexes_then_queries_with_metadata(tmp_path: Path) -> None:
    journals = tmp_path / "journals"
    journals.mkdir()
    journal = journals / "2026-08-03-library.md"
    journal.write_text(
        "# Library afternoon\nThe library displayed a fictional town map.\n",
        encoding="utf-8",
    )
    index_path = tmp_path / "indexes" / "journals.sqlite3"

    indexed = run_cli(str(journals), "--index", str(index_path))
    reindexed = run_cli(str(journals), "--index", str(index_path))
    queried = run_cli("--query", "library", "--index", str(index_path), "--limit", "1")

    assert indexed.returncode == 0
    assert indexed.stdout == "journals=1 | chunks=1 | indexed=1 | skipped=0\n"
    assert indexed.stderr == ""
    assert reindexed.returncode == 0
    assert reindexed.stdout == "journals=1 | chunks=1 | indexed=0 | skipped=1\n"
    assert reindexed.stderr == ""
    assert queried.returncode == 0
    assert "date=2026-08-03" in queried.stdout
    assert "source=2026-08-03-library.md" in queried.stdout
    assert "title=Library afternoon" in queried.stdout
    assert "chunk=0" in queried.stdout
    assert "text=The library displayed a fictional town map." in queried.stdout


def test_cli_reports_useful_errors(tmp_path: Path) -> None:
    result = run_cli(str(tmp_path / "missing"), "--index", str(tmp_path / "index.sqlite3"))

    assert result.returncode == 1
    assert result.stdout == ""
    assert "Journal directory does not exist or is not a directory" in result.stderr
