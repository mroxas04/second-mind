"""Contract tests for version-controlled synthetic journals."""

from datetime import date
from pathlib import Path
import re

from second_mind import load_journals


SAMPLE_DIRECTORY = Path(__file__).parents[1] / "data" / "sample_journals"
FILENAME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?\.md$"
)
SYNTHETIC_MARKER = "<!-- Synthetic sample journal entry; no real personal data. -->"


def sample_paths() -> list[Path]:
    """Return only the committed synthetic Markdown fixtures."""

    return sorted(SAMPLE_DIRECTORY.glob("*.md"))


def test_sample_set_is_small_and_present() -> None:
    assert len(sample_paths()) == 3


def test_sample_filenames_contain_valid_dates() -> None:
    for path in sample_paths():
        assert FILENAME_PATTERN.fullmatch(path.name)
        assert date.fromisoformat(path.name[:10])


def test_samples_are_marked_synthetic_and_have_content() -> None:
    for path in sample_paths():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        assert lines[0].startswith("# ")
        assert lines[0] != "# "
        assert SYNTHETIC_MARKER in text
        assert text.partition(SYNTHETIC_MARKER)[2].strip()


def test_sample_journals_load_in_chronological_order() -> None:
    entries = load_journals(SAMPLE_DIRECTORY)

    assert [entry.entry_date for entry in entries] == sorted(
        entry.entry_date for entry in entries
    )
    assert len(entries) == 3
