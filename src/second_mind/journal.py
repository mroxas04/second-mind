"""Journal domain types and Markdown loading functions."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import warnings


_FILENAME_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?\.md$"
)


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """A typed journal entry with its date and source identity."""

    entry_date: date
    title: str | None
    body: str
    source_path: Path


class JournalValidationError(ValueError):
    """Report why a Markdown file cannot be loaded as a journal entry."""


def load_journal(path: Path) -> JournalEntry:
    """Load one UTF-8 Markdown journal and validate its filename and body.

    The optional first Markdown H1 becomes the title. If it is present, only
    that line and its line terminator are removed; the rest of the body is
    preserved exactly.

    Raises:
        JournalValidationError: If the path does not satisfy the journal
            filename or content contract, cannot be read, or is not UTF-8.
    """

    entry_date = _date_from_filename(path)

    if not path.is_file():
        raise _validation_error(path, "path is not a readable file")

    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise _validation_error(path, "file is not valid UTF-8") from error
    except OSError as error:
        raise _validation_error(path, f"file could not be read: {error}") from error

    title, body = _title_and_body(path, text)
    if not body.strip():
        raise _validation_error(path, "journal body is empty")

    return JournalEntry(
        entry_date=entry_date,
        title=title,
        body=body,
        source_path=path,
    )


def load_journals(directory: Path) -> list[JournalEntry]:
    """Load valid Markdown journals from a directory in chronological order.

    Non-Markdown files and nested directories are ignored. Invalid Markdown
    journals produce an informative warning and do not prevent other entries
    from loading.

    Raises:
        NotADirectoryError: If ``directory`` is not an existing directory.
    """

    if not directory.is_dir():
        raise NotADirectoryError(
            f"Journal directory does not exist or is not a directory: {directory}"
        )

    entries: list[JournalEntry] = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix != ".md":
            continue

        try:
            entries.append(load_journal(path))
        except JournalValidationError as error:
            warnings.warn(f"Skipping {error}", UserWarning, stacklevel=2)

    return sorted(entries, key=lambda entry: (entry.entry_date, entry.source_path.name))


def _date_from_filename(path: Path) -> date:
    match = _FILENAME_PATTERN.fullmatch(path.name)
    if match is None:
        raise _validation_error(
            path,
            "filename must match YYYY-MM-DD-optional-slug.md",
        )

    date_text = match.group("date")
    try:
        return date.fromisoformat(date_text)
    except ValueError as error:
        raise _validation_error(
            path,
            f"date '{date_text}' is not a valid calendar date",
        ) from error


def _title_and_body(path: Path, text: str) -> tuple[str | None, str]:
    first_line, separator, remainder = text.partition("\n")
    title_line = first_line.removesuffix("\r")

    if not title_line.startswith("# "):
        return None, text

    title = title_line[2:].strip()
    if not title:
        raise _validation_error(path, "first-line H1 title is empty")

    body = remainder if separator else ""
    return title, body


def _validation_error(path: Path, reason: str) -> JournalValidationError:
    return JournalValidationError(f"Invalid journal '{path}': {reason}")
