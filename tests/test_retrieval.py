"""Tests for natural-language journal passage retrieval."""

from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pytest

from second_mind import JournalChunk
from second_mind.index import LocalVectorIndex
from second_mind.retrieval import retrieve_passages


class KeywordEmbedder:
    """Small deterministic embedding backend for retrieval tests."""

    @property
    def identifier(self) -> str:
        """Identify the test vector layout."""

        return "retrieval-keyword-test-v1"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Count selected synthetic keywords."""

        return [
            [
                float(text.casefold().count("library")),
                float(text.casefold().count("garden")),
            ]
            for text in texts
        ]


class CollisionEmbedder:
    """Rank an unrelated chunk above a relevant one for filtering tests."""

    @property
    def identifier(self) -> str:
        """Identify the deliberate collision layout."""

        return "retrieval-collision-test-v1"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Give the unrelated garden chunk the highest raw similarity."""

        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.casefold()
            if lowered == "library":
                vectors.append([1.0])
            elif "garden" in lowered:
                vectors.append([2.0])
            else:
                vectors.append([0.5])
        return vectors


def make_chunk(text: str, *, source: str, title: str) -> JournalChunk:
    """Build a synthetic journal chunk with citation metadata."""

    return JournalChunk(
        text=text,
        entry_date=date(2026, 9, 3),
        source_path=Path(source),
        title=title,
        chunk_index=0,
    )


def test_retrieve_passages_returns_relevant_text_with_citation(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "journals.sqlite3"
    index = LocalVectorIndex(index_path)
    index.add_chunks(
        [
            make_chunk(
                "The library displayed a fictional town map.",
                source="2026-09-03-library.md",
                title="Library afternoon",
            ),
            make_chunk(
                "The garden planter held basil.",
                source="2026-09-04-garden.md",
                title="Garden planning",
            ),
        ],
        KeywordEmbedder(),
    )

    passages = retrieve_passages(
        "What happened at the library?",
        index_path,
        limit=2,
        embedder=KeywordEmbedder(),
    )

    assert len(passages) == 1
    assert passages[0].chunk.text == (
        "The library displayed a fictional town map."
    )
    assert passages[0].citation == (
        "2026-09-03 | 2026-09-03-library.md | Library afternoon | chunk 0"
    )


def test_retrieve_passages_reports_insufficient_retrieval_evidence(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "journals.sqlite3"
    index = LocalVectorIndex(index_path)
    index.add_chunks(
        [
            make_chunk(
                "The garden planter held basil.",
                source="2026-09-04-garden.md",
                title="Garden planning",
            )
        ],
        KeywordEmbedder(),
    )

    passages = retrieve_passages(
        "What happened at the library?",
        index_path,
        embedder=KeywordEmbedder(),
    )

    assert passages == []


def test_lexical_gate_considers_candidates_beyond_requested_limit(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "journals.sqlite3"
    index = LocalVectorIndex(index_path)
    index.add_chunks(
        [
            make_chunk(
                "The library displayed a fictional town map.",
                source="2026-09-03-library.md",
                title="Library afternoon",
            ),
            make_chunk(
                "The garden planter held basil.",
                source="2026-09-04-garden.md",
                title="Garden planning",
            ),
        ],
        CollisionEmbedder(),
    )

    passages = retrieve_passages(
        "library",
        index_path,
        limit=1,
        embedder=CollisionEmbedder(),
    )

    assert len(passages) == 1
    assert passages[0].chunk.source_path.name == "2026-09-03-library.md"


@pytest.mark.parametrize(
    ("question", "limit", "minimum_score", "message"),
    [
        ("   ", 3, 0.0, "question must not be empty"),
        (
            "What did I do?",
            3,
            0.0,
            "question must include at least one searchable term",
        ),
        ("library", 0, 0.0, "limit must be greater than zero"),
        ("library", 3, -0.1, "minimum_score must not be negative"),
    ],
)
def test_retrieve_passages_validates_inputs(
    tmp_path: Path,
    question: str,
    limit: int,
    minimum_score: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        retrieve_passages(
            question,
            tmp_path / "journals.sqlite3",
            limit=limit,
            minimum_score=minimum_score,
            embedder=KeywordEmbedder(),
        )
