"""End-to-end tests for the stable local MVP command."""

from pathlib import Path
import subprocess
import sys


def run_app(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the package-level local MVP entry point."""

    return subprocess.run(
        [sys.executable, "-m", "second_mind", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def test_app_answers_multiple_questions_and_refuses_locally(
    tmp_path: Path,
) -> None:
    journals = tmp_path / "journals"
    journals.mkdir()
    (journals / "2026-11-03-library.md").write_text(
        "# Library afternoon\nThe library displayed a fictional town map.\n",
        encoding="utf-8",
    )
    index_path = tmp_path / "indexes" / "journals.sqlite3"

    result = run_app(
        str(journals),
        "--index",
        str(index_path),
        "--question",
        "What did the library display?",
        "--question",
        "Which mountain trail did I hike?",
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert "index journals=1 | chunks=1 | indexed=1 | skipped=0" in result.stdout
    assert "answer=The library displayed a fictional town map." in result.stdout
    assert (
        "citation=1 | 2026-11-03 | 2026-11-03-library.md | "
        "Library afternoon | chunk 0"
    ) in result.stdout
    assert "refusal=insufficient evidence in the indexed journals" in result.stdout


def test_app_reports_missing_journal_directory(tmp_path: Path) -> None:
    result = run_app(
        str(tmp_path / "missing"),
        "--index",
        str(tmp_path / "journals.sqlite3"),
        "--question",
        "What did the library display?",
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "Journal directory does not exist or is not a directory" in result.stderr
