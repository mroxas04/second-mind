"""Tests for typed Markdown journal ingestion."""

from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path

import pytest

from second_mind import JournalValidationError, load_journal, load_journals


def write_journal(path: Path, content: str) -> Path:
    """Write a synthetic journal fixture and return its path."""

    path.write_text(content, encoding="utf-8", newline="")
    return path


def test_load_journal_parses_a_valid_titled_journal(tmp_path: Path) -> None:
    path = write_journal(
        tmp_path / "2026-07-20-project-notes.md",
        "# Project notes\n\nFirst paragraph.\n\nSecond paragraph.\n",
    )

    entry = load_journal(path)

    assert entry.entry_date == date(2026, 7, 20)
    assert entry.title == "Project notes"
    assert entry.body == "\nFirst paragraph.\n\nSecond paragraph.\n"
    assert entry.source_path == path

    with pytest.raises(FrozenInstanceError):
        setattr(entry, "body", "Changed")


def test_load_journal_preserves_the_complete_body_without_an_h1(
    tmp_path: Path,
) -> None:
    body = "Opening thought.\n\n## A subsection\nDetails stay intact.\n"
    path = write_journal(tmp_path / "2026-07-19.md", body)

    entry = load_journal(path)

    assert entry.title is None
    assert entry.body == body
    assert entry.source_path == path


@pytest.mark.parametrize(
    ("filename", "message"),
    [
        ("journal.md", "filename must match"),
        ("2026-07-20-Bad-Slug.md", "filename must match"),
        ("2026-02-30-impossible.md", "not a valid calendar date"),
    ],
)
def test_load_journal_rejects_invalid_filenames(
    tmp_path: Path,
    filename: str,
    message: str,
) -> None:
    path = write_journal(tmp_path / filename, "A valid body.\n")

    with pytest.raises(JournalValidationError, match=message) as error:
        load_journal(path)

    assert str(path) in str(error.value)


@pytest.mark.parametrize(
    "content",
    [
        "",
        " \n\t\n",
        "# Title only\n",
        "# Title only\n\n",
    ],
)
def test_load_journal_rejects_an_empty_body(
    tmp_path: Path,
    content: str,
) -> None:
    path = write_journal(tmp_path / "2026-07-20-empty.md", content)

    with pytest.raises(JournalValidationError, match="journal body is empty"):
        load_journal(path)


def test_load_journals_loads_multiple_files_and_ignores_non_markdown(
    tmp_path: Path,
) -> None:
    write_journal(tmp_path / "2026-07-18-first.md", "First body.\n")
    write_journal(tmp_path / "2026-07-19-second.md", "# Second\nSecond body.\n")
    write_journal(tmp_path / "notes.txt", "Not a journal.\n")
    nested = tmp_path / "2026-07-20-nested.md"
    nested.mkdir()

    entries = load_journals(tmp_path)

    assert len(entries) == 2
    assert [entry.source_path.name for entry in entries] == [
        "2026-07-18-first.md",
        "2026-07-19-second.md",
    ]


def test_load_journals_orders_entries_chronologically(tmp_path: Path) -> None:
    write_journal(tmp_path / "2026-07-20-latest.md", "Latest.\n")
    write_journal(tmp_path / "2025-12-31-earliest.md", "Earliest.\n")
    write_journal(tmp_path / "2026-01-15-middle.md", "Middle.\n")

    entries = load_journals(tmp_path)

    assert [entry.entry_date for entry in entries] == [
        date(2025, 12, 31),
        date(2026, 1, 15),
        date(2026, 7, 20),
    ]


def test_load_journals_continues_after_an_invalid_file(tmp_path: Path) -> None:
    first = write_journal(tmp_path / "2026-07-18-first.md", "First.\n")
    invalid = write_journal(tmp_path / "not-a-journal.md", "Invalid name.\n")
    second = write_journal(tmp_path / "2026-07-20-second.md", "Second.\n")

    with pytest.warns(UserWarning, match="filename must match") as warnings:
        entries = load_journals(tmp_path)

    assert str(invalid) in str(warnings[0].message)
    assert [entry.source_path for entry in entries] == [first, second]
