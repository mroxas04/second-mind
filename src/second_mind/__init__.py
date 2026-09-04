"""Public package interface for Second Mind."""

from second_mind.chunking import JournalChunk, chunk_journal
from second_mind.embeddings import Embedder, HashingEmbedder
from second_mind.journal import (
    JournalEntry,
    JournalValidationError,
    load_journal,
    load_journals,
)
from second_mind.handwritten_import import (
    DraftImport,
    HandwrittenImportWorkspace,
    ImportState,
    OcrError,
    OcrObservation,
    approve_draft,
    recognize_staged_scan,
    stage_scan,
    write_draft,
)

__all__ = [
    "Embedder",
    "HashingEmbedder",
    "JournalChunk",
    "JournalEntry",
    "JournalValidationError",
    "DraftImport",
    "HandwrittenImportWorkspace",
    "ImportState",
    "OcrError",
    "OcrObservation",
    "approve_draft",
    "chunk_journal",
    "load_journal",
    "load_journals",
    "recognize_staged_scan",
    "stage_scan",
    "write_draft",
]
