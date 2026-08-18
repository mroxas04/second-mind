"""Local persistent journal indexing and similarity-query CLI."""

from argparse import ArgumentParser
from collections import defaultdict
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Iterator
import json
import sqlite3
import sys

from second_mind.chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    JournalChunk,
    chunk_journal,
)
from second_mind.embeddings import Embedder, HashingEmbedder
from second_mind.journal import load_journals


DEFAULT_INDEX_PATH = Path("data/indexes/journals.sqlite3")


@dataclass(frozen=True, slots=True)
class IndexingSummary:
    """Counts produced by one journal indexing run."""

    journals: int
    chunks: int
    indexed: int
    skipped: int


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A similarity score paired with a persisted journal chunk."""

    score: float
    chunk: JournalChunk


class LocalVectorIndex:
    """Persist journal vectors and metadata in a local SQLite file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    source TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    entry_date TEXT NOT NULL,
                    title TEXT,
                    text TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    embedding_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    PRIMARY KEY (source, chunk_index)
                )
                """
            )

    def add_chunks(
        self,
        chunks: Sequence[JournalChunk],
        embedder: Embedder,
    ) -> tuple[int, int]:
        """Insert or update chunks, returning ``(indexed, skipped)`` counts."""

        grouped: dict[str, list[JournalChunk]] = defaultdict(list)
        for chunk in chunks:
            grouped[str(chunk.source_path)].append(chunk)

        indexed = 0
        skipped = 0
        embedding_id = _embedding_id(embedder)
        with self._connect() as connection:
            for source, source_chunks in grouped.items():
                source_chunks.sort(key=lambda chunk: chunk.chunk_index)
                existing = {
                    row[0]: (row[1], row[2])
                    for row in connection.execute(
                        """
                        SELECT chunk_index, content_hash, embedding_id
                        FROM chunks
                        WHERE source = ?
                        """,
                        (source,),
                    )
                }

                pending: list[tuple[JournalChunk, str]] = []
                for chunk in source_chunks:
                    content_hash = _content_hash(chunk)
                    if existing.get(chunk.chunk_index) == (
                        content_hash,
                        embedding_id,
                    ):
                        skipped += 1
                    else:
                        pending.append((chunk, content_hash))

                vectors = embedder.embed(
                    [_embedding_text(chunk) for chunk, _ in pending]
                )
                if len(vectors) != len(pending):
                    raise ValueError("embedder returned an unexpected number of vectors")

                for (chunk, content_hash), vector in zip(pending, vectors, strict=True):
                    connection.execute(
                        """
                        INSERT INTO chunks (
                            source, chunk_index, entry_date, title, text,
                            embedding, embedding_id, content_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(source, chunk_index) DO UPDATE SET
                            entry_date = excluded.entry_date,
                            title = excluded.title,
                            text = excluded.text,
                            embedding = excluded.embedding,
                            embedding_id = excluded.embedding_id,
                            content_hash = excluded.content_hash
                        """,
                        (
                            source,
                            chunk.chunk_index,
                            chunk.entry_date.isoformat(),
                            chunk.title,
                            chunk.text,
                            json.dumps(vector, separators=(",", ":")),
                            embedding_id,
                            content_hash,
                        ),
                    )
                    indexed += 1

                retained = [chunk.chunk_index for chunk in source_chunks]
                placeholders = ",".join("?" for _ in retained)
                connection.execute(
                    f"""
                    DELETE FROM chunks
                    WHERE source = ? AND chunk_index NOT IN ({placeholders})
                    """,
                    (source, *retained),
                )

        return indexed, skipped

    def query(
        self,
        text: str,
        embedder: Embedder,
        *,
        limit: int = 3,
    ) -> list[SearchResult]:
        """Return the closest indexed chunks and their persisted metadata."""

        if not text.strip():
            raise ValueError("query text must not be empty")
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        query_vector = embedder.embed([text])[0]
        results: list[SearchResult] = []
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source, chunk_index, entry_date, title, text,
                       embedding, embedding_id
                FROM chunks
                """
            )
            for row in rows:
                (
                    source,
                    chunk_index,
                    entry_date,
                    title,
                    chunk_text,
                    raw,
                    embedding_id,
                ) = row
                if embedding_id != _embedding_id(embedder):
                    continue
                vector = json.loads(raw)
                if len(vector) != len(query_vector):
                    continue
                score = sum(
                    left * right
                    for left, right in zip(query_vector, vector, strict=True)
                )
                results.append(
                    SearchResult(
                        score=score,
                        chunk=JournalChunk(
                            text=chunk_text,
                            entry_date=_date_from_storage(entry_date),
                            source_path=Path(source),
                            title=title,
                            chunk_index=chunk_index,
                        ),
                    )
                )

        return sorted(
            results,
            key=lambda result: (
                -result.score,
                str(result.chunk.source_path),
                result.chunk.chunk_index,
            ),
        )[:limit]

    def count(self) -> int:
        """Return the number of persisted chunks."""

        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()
        return int(row[0])

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        try:
            with connection:
                yield connection
        finally:
            connection.close()


def index_journals(
    directory: Path,
    index_path: Path = DEFAULT_INDEX_PATH,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    embedder: Embedder | None = None,
) -> IndexingSummary:
    """Load, chunk, embed, and persist every valid journal in a directory."""

    entries = load_journals(directory)
    if not entries:
        raise ValueError(f"no valid journal entries found in '{directory}'")

    chunks = [
        chunk
        for entry in entries
        for chunk in chunk_journal(entry, chunk_size=chunk_size, overlap=overlap)
    ]
    index = LocalVectorIndex(index_path)
    indexed, skipped = index.add_chunks(chunks, embedder or HashingEmbedder())
    return IndexingSummary(
        journals=len(entries),
        chunks=len(chunks),
        indexed=indexed,
        skipped=skipped,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Index a journal directory or query the local index."""

    parser = ArgumentParser(
        prog="python -m second_mind.index",
        description="Build or query the local journal vector index.",
    )
    parser.add_argument("directory", nargs="?", type=Path)
    parser.add_argument("--query", help="query text instead of indexing journals")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    parser.add_argument("--limit", type=int, default=3)
    arguments = parser.parse_args(argv)

    try:
        if arguments.query is not None:
            if arguments.directory is not None:
                parser.error("directory cannot be used with --query")
            results = LocalVectorIndex(arguments.index).query(
                arguments.query,
                HashingEmbedder(),
                limit=arguments.limit,
            )
            if not results:
                print(
                    f"error: no compatible chunks found in '{arguments.index}'",
                    file=sys.stderr,
                )
                return 1
            _print_results(results)
            return 0

        if arguments.directory is None:
            parser.error("directory is required unless --query is used")
        summary = index_journals(
            arguments.directory,
            arguments.index,
            chunk_size=arguments.chunk_size,
            overlap=arguments.overlap,
        )
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        f"journals={summary.journals} | chunks={summary.chunks} | "
        f"indexed={summary.indexed} | skipped={summary.skipped}"
    )
    return 0


def _content_hash(chunk: JournalChunk) -> str:
    content = json.dumps(
        {
            "chunk_index": chunk.chunk_index,
            "date": chunk.entry_date.isoformat(),
            "text": chunk.text,
            "title": chunk.title,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(content.encode("utf-8")).hexdigest()


def _embedding_id(embedder: Embedder) -> str:
    return f"journal-title-text-v1|{embedder.identifier}"


def _embedding_text(chunk: JournalChunk) -> str:
    if chunk.title is None:
        return chunk.text
    return f"{chunk.title}\n\n{chunk.text}"


def _date_from_storage(value: str) -> date:
    return date.fromisoformat(value)


def _print_results(results: Sequence[SearchResult]) -> None:
    for position, result in enumerate(results):
        if position:
            print()
        print(f"score={result.score:.6f}")
        print(f"date={result.chunk.entry_date.isoformat()}")
        print(f"source={result.chunk.source_path.name}")
        if result.chunk.title is not None:
            print(f"title={result.chunk.title}")
        print(f"chunk={result.chunk.chunk_index}")
        print(f"text={result.chunk.text}")


if __name__ == "__main__":
    raise SystemExit(main())
