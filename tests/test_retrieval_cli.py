"""End-to-end tests for the cited natural-language retrieval CLI."""

from pathlib import Path
import subprocess
import sys


def run_module(module: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run a Second Mind module in the active test environment."""

    return subprocess.run(
        [sys.executable, "-m", module, *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def test_retrieval_cli_returns_passage_and_citation(tmp_path: Path) -> None:
    journals = tmp_path / "journals"
    journals.mkdir()
    journal = journals / "2026-09-03-library.md"
    journal.write_text(
        "# Library afternoon\nThe library displayed a fictional town map.\n",
        encoding="utf-8",
    )
    unrelated = journals / "2026-09-04-garden.md"
    unrelated.write_text(
        "# Garden planning\nThe basil planter moved beside the window.\n",
        encoding="utf-8",
    )
    index_path = tmp_path / "indexes" / "journals.sqlite3"

    indexed = run_module(
        "second_mind.index",
        str(journals),
        "--index",
        str(index_path),
    )
    retrieved = run_module(
        "second_mind.retrieval",
        "What",
        "did",
        "the",
        "library",
        "display?",
        "--index",
        str(index_path),
        "--limit",
        "1",
    )

    assert indexed.returncode == 0
    assert retrieved.returncode == 0
    assert "passage=1" in retrieved.stdout
    assert "text=The library displayed a fictional town map." in retrieved.stdout
    assert (
        "citation=2026-09-03 | 2026-09-03-library.md | "
        "Library afternoon | chunk 0"
    ) in retrieved.stdout
    assert "Garden planning" not in retrieved.stdout
    assert retrieved.stderr == ""


def test_retrieval_cli_refuses_to_return_zero_evidence(tmp_path: Path) -> None:
    result = run_module(
        "second_mind.retrieval",
        "What",
        "did",
        "the",
        "library",
        "display?",
        "--index",
        str(tmp_path / "empty.sqlite3"),
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "no relevant passages found" in result.stderr
