"""Stable local MVP workflow for indexing and grounded journal questions."""

from argparse import ArgumentParser
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import sys

from second_mind.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from second_mind.embeddings import Embedder, HashingEmbedder
from second_mind.index import DEFAULT_INDEX_PATH, IndexingSummary, index_journals
from second_mind.retrieval import (
    DEFAULT_MINIMUM_SCORE,
    RetrievedPassage,
    retrieve_passages,
)


REFUSAL_MESSAGE = "insufficient evidence in the indexed journals"


@dataclass(frozen=True, slots=True)
class GroundedResponse:
    """An extractive local answer or an explicit insufficient-evidence refusal."""

    question: str
    passages: tuple[RetrievedPassage, ...]

    @property
    def refused(self) -> bool:
        """Return whether the indexed journals supplied no supporting passage."""

        return not self.passages

    @property
    def answer(self) -> str | None:
        """Return the top retrieved passage as a conservative grounded answer."""

        if self.refused:
            return None
        return self.passages[0].chunk.text


@dataclass(frozen=True, slots=True)
class MvpSession:
    """Index-refresh evidence and responses from one local MVP run."""

    indexing: IndexingSummary
    responses: tuple[GroundedResponse, ...]


def run_session(
    journal_directory: Path,
    questions: Sequence[str],
    index_path: Path = DEFAULT_INDEX_PATH,
    *,
    limit: int = 1,
    minimum_score: float = DEFAULT_MINIMUM_SCORE,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    embedder: Embedder | None = None,
) -> MvpSession:
    """Refresh the local index and answer one or more questions from it.

    Answers are extractive: the top supporting journal passage is returned
    unchanged with its source citation. Questions without supporting lexical
    evidence produce a refusal instead of an invented answer.
    """

    normalized_questions = tuple(question.strip() for question in questions)
    if not normalized_questions:
        raise ValueError("at least one question is required")
    if any(not question for question in normalized_questions):
        raise ValueError("questions must not be empty")

    active_embedder = embedder or HashingEmbedder()
    indexing = index_journals(
        journal_directory,
        index_path,
        chunk_size=chunk_size,
        overlap=overlap,
        embedder=active_embedder,
    )
    responses = tuple(
        GroundedResponse(
            question=question,
            passages=tuple(
                retrieve_passages(
                    question,
                    index_path,
                    limit=limit,
                    minimum_score=minimum_score,
                    embedder=active_embedder,
                )
            ),
        )
        for question in normalized_questions
    )
    return MvpSession(indexing=indexing, responses=responses)


def main(argv: Sequence[str] | None = None) -> int:
    """Refresh a local journal index and answer repeated grounded questions."""

    parser = ArgumentParser(
        prog="second-mind",
        description=(
            "Refresh a local journal index, answer from cited passages, and "
            "refuse questions without supporting evidence."
        ),
    )
    parser.add_argument("journal_directory", type=Path)
    parser.add_argument(
        "--question",
        action="append",
        required=True,
        help="question to answer; repeat this option for multiple questions",
    )
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument(
        "--minimum-score",
        type=float,
        default=DEFAULT_MINIMUM_SCORE,
    )
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    arguments = parser.parse_args(argv)

    try:
        session = run_session(
            arguments.journal_directory,
            arguments.question,
            arguments.index,
            limit=arguments.limit,
            minimum_score=arguments.minimum_score,
            chunk_size=arguments.chunk_size,
            overlap=arguments.overlap,
        )
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    _print_session(session)
    return 0


def _print_session(session: MvpSession) -> None:
    summary = session.indexing
    print(
        f"index journals={summary.journals} | chunks={summary.chunks} | "
        f"indexed={summary.indexed} | skipped={summary.skipped}"
    )
    for position, response in enumerate(session.responses, start=1):
        print()
        print(f"question={position} | text={response.question}")
        if response.refused:
            print(f"refusal={REFUSAL_MESSAGE}")
            continue
        print(f"answer={response.answer}")
        for passage_position, passage in enumerate(response.passages, start=1):
            print(f"citation={passage_position} | {passage.citation}")
            print(f"score={passage.score:.6f}")


if __name__ == "__main__":
    raise SystemExit(main())
