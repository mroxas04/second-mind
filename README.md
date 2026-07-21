# Second Mind

Second Mind is a local-first personal knowledge system for turning typed journal
entries into grounded answers with dates and source citations.

## Current status

The current July foundation and typed-ingestion milestone covers only the
repository foundation, privacy model, journal file contract, typed journal
domain model, synthetic sample data, and a working test command.

The immediately following July slice will add:

```python
load_journal(path: Path) -> JournalEntry
load_journals(directory: Path) -> list[JournalEntry]
```

Those ingestion functions are intentionally not implemented in this pass.

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
and `2026-07-20-project-notes.md` are valid examples. A future loader will
extract an optional title from the first Markdown H1 (`# Title`). The remaining
Markdown content will become the body. Files do not use YAML front matter, so
the project does not need a YAML dependency.

The typed domain model is `second_mind.JournalEntry`, with an entry date,
optional title, body, and source path. Loading files into that model belongs to
the next implementation slice.

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
`environment.yml` selects Python and pip, then installs that requirements file.
`pyproject.toml` contains pytest configuration without duplicating dependencies.

## Repository layout

```text
data/sample_journals/   Synthetic, version-controlled journal fixtures
data/private_journals/  Ignored location for real local journal entries
src/second_mind/        Python package and journal domain model
tests/                  Foundation and sample-contract tests
```

## Current non-goals

This milestone does not include file-loading functions, embeddings, RAG, OCR,
a vector database, an LLM interface, agents, a web UI or framework, cloud
services, generated indexes, or model downloads.
