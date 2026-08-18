"""Public package interface for Second Mind."""

from second_mind.chunking import JournalChunk, chunk_journal
from second_mind.embeddings import Embedder, HashingEmbedder
from second_mind.journal import (
    JournalEntry,
    JournalValidationError,
    load_journal,
    load_journals,
)

__all__ = [
    "Embedder",
    "HashingEmbedder",
    "JournalChunk",
    "JournalEntry",
    "JournalValidationError",
    "chunk_journal",
    "load_journal",
    "load_journals",
]
