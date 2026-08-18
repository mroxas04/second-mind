"""Tests for persistent local journal indexing and retrieval."""

from collections.abc import Sequence
from datetime import date
from pathlib import Path

from second_mind import JournalChunk
from second_mind.index import LocalVectorIndex, index_journals


class KeywordEmbedder:
    """Small deterministic embedding backend for index tests."""

    @property
    def identifier(self) -> str:
        """Identify the test vector layout."""

        return "keyword-test-v1"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Count selected synthetic keywords."""

        return [
            [
                float(text.casefold().count("library")),
                float(text.casefold().count("garden")),
                float(text.casefold().count("cooking")),
            ]
            for text in texts
        ]


def make_chunk(
    text: str,
    *,
    source: str = "2026-08-03-library.md",
    chunk_index: int = 0,
) -> JournalChunk:
    """Build a synthetic journal chunk."""

    return JournalChunk(
        text=text,
        entry_date=date(2026, 8, 3),
        source_path=Path(source),
        title="Library afternoon",
        chunk_index=chunk_index,
    )


def write_journal(path: Path, text: str) -> None:
    """Write a synthetic journal fixture."""

    path.write_text(text, encoding="utf-8")


def test_chunks_round_trip_through_the_index_with_metadata(tmp_path: Path) -> None:
    index_path = tmp_path / "indexes" / "journals.sqlite3"
    index = LocalVectorIndex(index_path)
    chunk = make_chunk("The library display featured local history.")

    indexed, skipped = index.add_chunks([chunk], KeywordEmbedder())
    results = index.query("library", KeywordEmbedder(), limit=1)

    assert index_path.is_file()
    assert (indexed, skipped) == (1, 0)
    assert len(results) == 1
    assert results[0].score > 0.0
    assert results[0].chunk == chunk


def test_reindexing_the_same_source_does_not_duplicate_chunks(tmp_path: Path) -> None:
    index = LocalVectorIndex(tmp_path / "journals.sqlite3")
    chunks = [
        make_chunk("library one", chunk_index=0),
        make_chunk("library two", chunk_index=1),
    ]

    assert index.add_chunks(chunks, KeywordEmbedder()) == (2, 0)
    assert index.add_chunks(chunks, KeywordEmbedder()) == (0, 2)
    assert index.count() == 2


def test_changed_source_replaces_and_prunes_old_chunks(tmp_path: Path) -> None:
    index = LocalVectorIndex(tmp_path / "journals.sqlite3")
    original = [
        make_chunk("library one", chunk_index=0),
        make_chunk("library two", chunk_index=1),
    ]
    replacement = [make_chunk("garden replacement", chunk_index=0)]

    index.add_chunks(original, KeywordEmbedder())
    indexed, skipped = index.add_chunks(replacement, KeywordEmbedder())

    assert (indexed, skipped) == (1, 0)
    assert index.count() == 1
    assert index.query("garden", KeywordEmbedder(), limit=1)[0].chunk.text == (
        "garden replacement"
    )


def test_multiple_journal_files_can_be_indexed(tmp_path: Path) -> None:
    journals = tmp_path / "journals"
    journals.mkdir()
    write_journal(journals / "2026-08-01-library.md", "# Library\nLibrary visit.\n")
    write_journal(journals / "2026-08-02-garden.md", "# Garden\nGarden planning.\n")
    index_path = tmp_path / "indexes" / "journals.sqlite3"

    summary = index_journals(
        journals,
        index_path,
        chunk_size=100,
        overlap=10,
        embedder=KeywordEmbedder(),
    )

    assert summary.journals == 2
    assert summary.chunks == 2
    assert summary.indexed == 2
    assert summary.skipped == 0
    assert LocalVectorIndex(index_path).count() == 2
