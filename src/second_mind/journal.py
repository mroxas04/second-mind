"""Journal domain types."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """A typed journal entry with its date and source identity."""

    entry_date: date
    title: str | None
    body: str
    source_path: Path
