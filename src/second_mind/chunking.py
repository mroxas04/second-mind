"""Deterministic chunking for parsed journal entries."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from second_mind.journal import JournalEntry


DEFAULT_CHUNK_SIZE = 1_000
DEFAULT_CHUNK_OVERLAP = 100
_BOUNDARIES = ("\n\n", "\n", " ")


@dataclass(frozen=True, slots=True)
class JournalChunk:
    """A journal body passage with citation metadata."""

    text: str
    entry_date: date
    source_path: Path
    title: str | None
    chunk_index: int


def chunk_journal(
    entry: JournalEntry,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[JournalChunk]:
    """Split a parsed journal body into ordered, overlapping chunks.

    ``chunk_size`` and ``overlap`` are measured in characters. Split points
    prefer paragraph, line, and word boundaries in that order. Journal parsing
    remains the responsibility of :func:`second_mind.load_journal`.
    """

    _validate_settings(chunk_size, overlap)
    text = entry.body.strip()
    chunks: list[JournalChunk] = []
    start = 0

    while start < len(text):
        end = _chunk_end(text, start, chunk_size)
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                JournalChunk(
                    text=chunk_text,
                    entry_date=entry.entry_date,
                    source_path=entry.source_path,
                    title=entry.title,
                    chunk_index=len(chunks),
                )
            )

        if end == len(text):
            break
        start = _next_start(text, start, end, overlap)

    return chunks


def _validate_settings(chunk_size: int, overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0:
        raise ValueError("overlap must not be negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")


def _chunk_end(text: str, start: int, chunk_size: int) -> int:
    maximum = min(start + chunk_size, len(text))
    if maximum == len(text):
        return maximum

    minimum = start + max(1, chunk_size // 2)
    for boundary in _BOUNDARIES:
        position = text.rfind(boundary, minimum, maximum)
        if position != -1:
            return position + len(boundary)
    return maximum


def _next_start(text: str, start: int, end: int, overlap: int) -> int:
    if overlap == 0:
        return end

    desired = max(start + 1, end - overlap)
    for boundary in _BOUNDARIES:
        position = text.find(boundary, desired, end)
        if position != -1:
            candidate = position + len(boundary)
            if candidate < end:
                return candidate
    return desired
