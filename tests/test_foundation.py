"""Foundation tests for the Second Mind package."""

from datetime import date
from pathlib import Path

from second_mind import JournalEntry


def test_journal_entry_represents_a_titled_entry() -> None:
    entry = JournalEntry(
        entry_date=date(2026, 7, 3),
        title="Library visit",
        body="I picked up a reserved novel.",
        source_path=Path("data/sample_journals/2026-07-03-library-visit.md"),
    )

    assert entry.entry_date == date(2026, 7, 3)
    assert entry.title == "Library visit"
    assert entry.body == "I picked up a reserved novel."
    assert entry.source_path.name == "2026-07-03-library-visit.md"


def test_journal_entry_title_is_optional() -> None:
    entry = JournalEntry(
        entry_date=date(2026, 7, 20),
        title=None,
        body="A journal entry does not require a heading.",
        source_path=Path("2026-07-20.md"),
    )

    assert entry.title is None
