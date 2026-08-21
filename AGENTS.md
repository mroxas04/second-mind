# Second Mind contributor guidance

## Project purpose

Second Mind is a local-first personal system for ingesting typed journal files,
retrieving relevant passages, and eventually generating answers grounded in
dated source entries. Privacy and evidence traceability are core requirements.

## MVP definition

The MVP must:

- Ingest local typed journal files.
- Automatically chunk, embed, and index entries.
- Accept natural-language questions.
- Retrieve relevant journal passages.
- Generate grounded answers.
- Cite source entries and dates.
- Refuse to answer when evidence is insufficient.
- Run locally.
- Pass a five-question retrieval test.

## Current milestone

The current December maintenance milestone builds directly on the stabilized
local MVP and is limited to:

- Keeping the stable MVP command as the repeatable workflow for adding new
  journal entries and refreshing the local index.
- Creating timestamped backup snapshots in an explicitly selected local or
  mounted external-drive destination.
- Copying the journal directory and current SQLite index without logging journal
  contents.
- Recording relative paths, file sizes, roles, and SHA-256 checksums in a local
  manifest.
- Verifying every copied file against the manifest before completing a backup.
- Refusing to overwrite an existing snapshot or place a backup inside the
  journal directory.
- Providing focused create and verify backup commands.
- Documenting the repeatable local backup workflow and its privacy boundaries.
- Testing the backup workflow offline using only fictional journal entries and
  synthetic index files.

The public backup interfaces are:

```python
create_backup(
    journal_directory: Path,
    destination: Path,
    index_path: Path = DEFAULT_INDEX_PATH,
    *,
    snapshot_name: str | None = None,
) -> BackupSummary

verify_backup(snapshot_path: Path) -> BackupVerification
```

The local backup commands are:

```bash
python -m second_mind.backup create \
  data/sample_journals /path/to/local/backups \
  --index data/indexes/journals.sqlite3

python -m second_mind.backup verify /path/to/local/backup-snapshot
```

The public stabilized workflow is:

```python
run_session(
    journal_directory: Path,
    questions: Sequence[str],
    index_path: Path = DEFAULT_INDEX_PATH,
) -> MvpSession
```

The local MVP command is:

```bash
python -m second_mind data/sample_journals \
  --question "What reserved book did I pick up?"
```

The public ingestion interface is:

```python
load_journal(path: Path) -> JournalEntry
load_journals(directory: Path) -> list[JournalEntry]
```

Keep this ingestion layer limited to parsing and validation.

The inspection command is:

```bash
python -m second_mind.ingest data/sample_journals
```

The CLI must reuse `load_journals`, preserve its validation warnings on standard
error, and avoid duplicating parsing logic.

## Journal data contract

- Journal entries are UTF-8 Markdown files.
- Filenames follow `YYYY-MM-DD-optional-slug.md`.
- The ISO date at the beginning of the filename is the authoritative entry date.
- The slug is optional and uses lowercase words separated by hyphens.
- The first Markdown H1 is the optional title.
- An entry without an H1 has `title=None`.
- The remaining Markdown content is the journal body.
- Do not add YAML front matter or a YAML dependency.
- Preserve the source path so later answers can cite the entry and date.

## Privacy rules

- Never inspect, commit, copy, summarize, log, or transmit real private journal
  content.
- Treat everything under `data/private_journals/` and legacy `notes/` paths as
  private, even when a task does not explicitly repeat this warning.
- Use only clearly fictional content in `data/sample_journals/` and tests.
- Keep private journals, generated indexes, model files, secrets, caches, and
  local environment files ignored by Git.
- Do not add cloud storage, telemetry, or network transmission of journal data.
- Avoid tests or commands that recursively inspect private-data directories.

## Coding standards

- Target Python 3.14 and use modern type hints.
- Use the `src` package layout.
- Prefer the standard library and `pathlib.Path`.
- Keep modules and functions small, explicit, and testable.
- Use UTF-8 for text files.
- Add docstrings to public modules, classes, and functions.
- Keep `requirements.txt` as the single source of truth for pip dependencies.
- Add a dependency only when the current milestone genuinely needs it.
- Do not introduce an application framework or cloud service.
- If a future embedding, inference, or vector-store dependency does not support
  Python 3.14, reassess the Python version before adding compatibility hacks.

## Testing

Create and activate the environment, then run:

```bash
conda env create -f environment.yml
conda activate second-mind
pytest
```

For an existing environment, update it with:

```bash
conda env update -f environment.yml --prune
```

Tests may inspect synthetic samples but must never inspect private journal files.

## Explicit non-goals for the current milestone

Do not add or implement:

- OCR or image processing.
- An LLM interface or model integration.
- Agents or orchestration.
- A web framework, API server, or web UI.
- Cloud services or telemetry.
- Production ingestion pipelines.
- Metadata beyond what is needed to identify, order, persist, and retrieve
  journal chunks with their date, title, source, and text.
- Model downloads or platform-specific Conda lockfiles.
- Conversational RAG, abstractive answer synthesis, or an LLM interface.
- Real or private journal evaluation, usage logging, and broader refusal-policy
  work.
- Restore automation or a clean restore rehearsal; those remain part of M059.
- Scheduled or background backups.
- Cloud backup services, application-managed encryption, or key management.
- Knowledge graphs, summarization, reranking, hybrid search, background
  watchers, or filesystem automation.
