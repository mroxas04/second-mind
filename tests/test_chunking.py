"""Tests for deterministic journal chunking and metadata attachment."""

from datetime import date
from pathlib import Path

import pytest

from second_mind import JournalEntry, chunk_journal


def make_entry(body: str) -> JournalEntry:
    """Build a synthetic parsed journal entry."""

    return JournalEntry(
        entry_date=date(2026, 8, 2),
        title="Synthetic walk",
        body=body,
        source_path=Path("2026-08-02-synthetic-walk.md"),
    )


def test_chunking_is_deterministic_and_preserves_metadata() -> None:
    entry = make_entry("alpha beta gamma delta epsilon zeta eta theta")

    first = chunk_journal(entry, chunk_size=24, overlap=10)
    second = chunk_journal(entry, chunk_size=24, overlap=10)

    assert first == second
    assert [chunk.text for chunk in first] == [
        "alpha beta gamma delta",
        "delta epsilon zeta eta",
        "zeta eta theta",
    ]
    assert [chunk.chunk_index for chunk in first] == [0, 1, 2]
    assert all(chunk.entry_date == entry.entry_date for chunk in first)
    assert all(chunk.source_path == entry.source_path for chunk in first)
    assert all(chunk.title == entry.title for chunk in first)


def test_zero_overlap_does_not_repeat_boundary_words() -> None:
    chunks = chunk_journal(
        make_entry("alpha beta gamma delta epsilon"),
        chunk_size=17,
        overlap=0,
    )

    assert [chunk.text for chunk in chunks] == [
        "alpha beta gamma",
        "delta epsilon",
    ]


def test_large_valid_overlap_still_advances_in_source_order() -> None:
    chunks = chunk_journal(
        make_entry("one two three four five six seven eight nine ten"),
        chunk_size=12,
        overlap=11,
    )

    assert chunks
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert chunks[-1].text.endswith("ten")


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(0, 0), (10, -1), (10, 10), (10, 11)],
)
def test_chunking_rejects_invalid_settings(chunk_size: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        chunk_journal(make_entry("synthetic text"), chunk_size=chunk_size, overlap=overlap)
