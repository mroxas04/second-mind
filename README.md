# Second Mind

Second Mind is a local-first personal knowledge system for turning typed journal
entries into grounded answers with dates and source citations.

## Current status

The current July typed-ingestion milestone includes the repository foundation,
privacy model, journal file contract, immutable journal domain model, synthetic
sample data, and two typed Markdown loading functions:

```python
load_journal(path: Path) -> JournalEntry
load_journals(directory: Path) -> list[JournalEntry]
```

`load_journal` validates and loads one journal. `load_journals` ignores
non-Markdown files, warns and continues when a Markdown journal is invalid, and
returns valid entries in chronological order.

Inspect what the directory loader parsed:

```bash
python -m second_mind.ingest data/sample_journals
```

The command prints each valid entry's date, optional title, source filename, and
body character count in chronological order. Validation warnings remain on
standard error. It exits successfully when at least one valid entry loads, and
exits with status 1 for an invalid directory or when no valid entries load.

## MVP definition

The eventual local MVP will:

- Ingest local typed journal files.
- Automatically chunk, embed, and index entries.
- Accept natural-language questions.
- Retrieve relevant journal passages.
- Generate grounded answers.
- Cite source entries and dates.
- Refuse to answer when evidence is insufficient.
- Run locally.
- Pass a five-question retrieval test.

## Journal file contract

Journal entries are UTF-8 Markdown files named:

```text
YYYY-MM-DD-optional-slug.md
```

The date is authoritative and comes from the filename. Both `2026-07-20.md`
and `2026-07-20-project-notes.md` are valid examples. The loader extracts an
optional title from the first Markdown H1 (`# Title`). When a title is present,
only that line and its line terminator are removed; all remaining text is
preserved as the body. Without an H1, the complete file is the body. Files do
not use YAML front matter, so the project does not need a YAML dependency.

The typed domain model is `second_mind.JournalEntry`, with an entry date,
optional title, body, and source path.

## Privacy

- Put only fictional, synthetic entries in `data/sample_journals/`.
- Put real journal files in `data/private_journals/`; Git ignores its contents.
- Never commit, inspect, log, or transmit real private journal content.
- Keep generated indexes, model files, secrets, and local environment files out
  of Git.
- The project is local-first and does not use cloud services.

## Environment

Create and activate the Python 3.14 Conda environment:

```bash
conda env create -f environment.yml
conda activate second-mind
```

Update an existing environment after dependency changes:

```bash
conda env update -f environment.yml --prune
conda activate second-mind
```

Run the test suite:

```bash
pytest
```

`requirements.txt` is the single source of truth for pip dependencies.
`environment.yml` selects Python and pip, installs that requirements file, and
installs this project in editable mode so its module commands are available.
`pyproject.toml` contains package and pytest configuration without duplicating
runtime dependencies.

## Repository layout

```text
data/sample_journals/   Synthetic, version-controlled journal fixtures
data/private_journals/  Ignored location for real local journal entries
src/second_mind/        Python package, journal domain model, and inspection CLI
tests/                  Foundation, ingestion, sample-contract, and CLI tests
```

## Current non-goals

This milestone does not include chunking, embeddings, retrieval, RAG, OCR, a
vector database, an LLM interface, agents, a web UI or framework, cloud
services, generated indexes, model downloads, or metadata beyond date, title,
path, and body.
