"""Command-line inspection for typed journal ingestion."""

from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path
import sys

from second_mind import load_journals


def main(argv: Sequence[str] | None = None) -> int:
    """Load a journal directory and print one summary per valid entry."""

    parser = ArgumentParser(
        prog="python -m second_mind.ingest",
        description="Inspect parsed Markdown journal entries.",
    )
    parser.add_argument("directory", type=Path, help="directory of journal files")
    arguments = parser.parse_args(argv)

    try:
        entries = load_journals(arguments.directory)
    except NotADirectoryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if not entries:
        print(
            f"error: no valid journal entries found in '{arguments.directory}'",
            file=sys.stderr,
        )
        return 1

    for entry in entries:
        title = entry.title if entry.title is not None else "<none>"
        print(
            f"date={entry.entry_date.isoformat()} | "
            f"title={title} | "
            f"source={entry.source_path.name} | "
            f"body_chars={len(entry.body)}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
