"""Tests for the stable local MVP workflow."""

from collections.abc import Sequence
from pathlib import Path

import pytest

from second_mind.app import run_session


class KeywordEmbedder:
    """Small deterministic embedding backend for MVP workflow tests."""

    @property
    def identifier(self) -> str:
        """Identify the test vector layout."""

        return "app-keyword-test-v1"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Count selected fictional keywords."""

        return [
            [
                float(text.casefold().count("library")),
                float(text.casefold().count("garden")),
            ]
            for text in texts
        ]


def write_sample_journal(directory: Path) -> None:
    """Write one fictional journal for a local MVP test."""

    directory.mkdir()
    (directory / "2026-11-03-library.md").write_text(
        "# Library afternoon\nThe library displayed a fictional town map.\n",
        encoding="utf-8",
    )


def test_session_refreshes_index_answers_and_refuses(tmp_path: Path) -> None:
    journals = tmp_path / "journals"
    write_sample_journal(journals)

    session = run_session(
        journals,
        [
            "What did the library display?",
            "Which mountain trail did I hike?",
        ],
        tmp_path / "indexes" / "journals.sqlite3",
        embedder=KeywordEmbedder(),
    )

    assert session.indexing.journals == 1
    assert session.indexing.indexed == 1
    answered, refused = session.responses
    assert answered.answer == "The library displayed a fictional town map."
    assert answered.passages[0].citation == (
        "2026-11-03 | 2026-11-03-library.md | Library afternoon | chunk 0"
    )
    assert not answered.refused
    assert refused.refused
    assert refused.answer is None


def test_session_reuses_unchanged_persistent_index(tmp_path: Path) -> None:
    journals = tmp_path / "journals"
    write_sample_journal(journals)
    index_path = tmp_path / "journals.sqlite3"

    first = run_session(
        journals,
        ["library"],
        index_path,
        embedder=KeywordEmbedder(),
    )
    second = run_session(
        journals,
        ["library"],
        index_path,
        embedder=KeywordEmbedder(),
    )

    assert (first.indexing.indexed, first.indexing.skipped) == (1, 0)
    assert (second.indexing.indexed, second.indexing.skipped) == (0, 1)
    assert second.responses[0].answer == first.responses[0].answer


@pytest.mark.parametrize(
    ("questions", "message"),
    [
        ([], "at least one question is required"),
        (["   "], "questions must not be empty"),
    ],
)
def test_session_requires_non_empty_questions(
    tmp_path: Path,
    questions: list[str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        run_session(tmp_path, questions, tmp_path / "journals.sqlite3")
