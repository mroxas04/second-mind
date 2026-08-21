"""Natural-language passage retrieval with explicit journal citations."""

from argparse import ArgumentParser
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
import sys

from second_mind.chunking import JournalChunk
from second_mind.embeddings import Embedder, HashingEmbedder
from second_mind.index import DEFAULT_INDEX_PATH, LocalVectorIndex


DEFAULT_MINIMUM_SCORE = 0.0
_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
_QUESTION_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
        "but",
        "by",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "hers",
        "him",
        "his",
        "how",
        "i",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "mine",
        "my",
        "of",
        "on",
        "or",
        "our",
        "ours",
        "she",
        "so",
        "that",
        "the",
        "their",
        "theirs",
        "them",
        "they",
        "this",
        "those",
        "to",
        "up",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "you",
        "your",
        "yours",
    }
)


@dataclass(frozen=True, slots=True)
class RetrievedPassage:
    """A relevant journal passage paired with its citation and score."""

    score: float
    chunk: JournalChunk

    @property
    def citation(self) -> str:
        """Return a stable human-readable citation for the source chunk."""

        parts = [
            self.chunk.entry_date.isoformat(),
            self.chunk.source_path.name,
        ]
        if self.chunk.title is not None:
            parts.append(self.chunk.title)
        parts.append(f"chunk {self.chunk.chunk_index}")
        return " | ".join(parts)


def retrieve_passages(
    question: str,
    index_path: Path = DEFAULT_INDEX_PATH,
    *,
    limit: int = 3,
    minimum_score: float = DEFAULT_MINIMUM_SCORE,
    embedder: Embedder | None = None,
) -> list[RetrievedPassage]:
    """Return evidence-positive journal passages for a natural-language question.

    This function performs retrieval only. It does not synthesize an answer or
    send journal content to a hosted service.
    """

    if not question.strip():
        raise ValueError("question must not be empty")
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    if minimum_score < 0:
        raise ValueError("minimum_score must not be negative")

    search_terms = _search_terms(question)
    if not search_terms:
        raise ValueError("question must include at least one searchable term")

    index = LocalVectorIndex(index_path)
    results = index.query(
        " ".join(search_terms),
        embedder or HashingEmbedder(),
        limit=max(limit, index.count()),
    )
    passages = [
        RetrievedPassage(score=result.score, chunk=result.chunk)
        for result in results
        if result.score > minimum_score
        and _has_lexical_evidence(search_terms, result.chunk)
    ]
    return passages[:limit]


def main(argv: Sequence[str] | None = None) -> int:
    """Retrieve cited journal passages for one natural-language question."""

    parser = ArgumentParser(
        prog="python -m second_mind.retrieval",
        description="Retrieve locally indexed journal passages with citations.",
    )
    parser.add_argument("question", nargs="+", help="natural-language question")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument(
        "--minimum-score",
        type=float,
        default=DEFAULT_MINIMUM_SCORE,
        help="exclude passages at or below this similarity score",
    )
    arguments = parser.parse_args(argv)

    try:
        passages = retrieve_passages(
            " ".join(arguments.question),
            arguments.index,
            limit=arguments.limit,
            minimum_score=arguments.minimum_score,
        )
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if not passages:
        print(
            "error: no relevant passages found; try a more specific question "
            "or verify that the journal index is current",
            file=sys.stderr,
        )
        return 1

    _print_passages(passages)
    return 0


def _print_passages(passages: Sequence[RetrievedPassage]) -> None:
    for position, passage in enumerate(passages, start=1):
        if position > 1:
            print()
        print(f"passage={position}")
        print(f"text={passage.chunk.text}")
        print(f"citation={passage.citation}")
        print(f"score={passage.score:.6f}")


def _search_terms(question: str) -> list[str]:
    return [
        token
        for token in _TOKEN_PATTERN.findall(question.casefold())
        if token not in _QUESTION_STOPWORDS
    ]


def _has_lexical_evidence(
    search_terms: Sequence[str],
    chunk: JournalChunk,
) -> bool:
    searchable_text = chunk.text
    if chunk.title is not None:
        searchable_text = f"{chunk.title}\n{searchable_text}"
    chunk_terms = set(_TOKEN_PATTERN.findall(searchable_text.casefold()))
    return any(term in chunk_terms for term in search_terms)


if __name__ == "__main__":
    raise SystemExit(main())
