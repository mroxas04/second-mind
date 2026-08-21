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

The current October five-question retrieval evaluation builds directly on the
completed typed-ingestion, local-indexing, and cited-retrieval layers and is
limited to:

- Loading exactly five natural-language evaluation cases from a small local
  JSON file.
- Building a fresh temporary local index for every evaluation run.
- Scoring top-passage retrieval accuracy for evidence-positive questions.
- Scoring journal date, source filename, optional title, and chunk-order
  citation accuracy.
- Scoring appropriate refusal for a question with no supporting passage.
- Returning a failing command-line exit status when any applicable criterion
  misses.
- Keeping the committed evaluation privacy-safe by using only fictional entries
  in `data/sample_journals/`.
- Keeping evaluation local and deterministic without hosted APIs, telemetry, or
  journal-data transmission.

The public evaluation interface is:

```python
evaluate_retrieval(
    journal_directory: Path,
    cases_path: Path,
) -> EvaluationSummary
```

The sample evaluation command is:

```bash
python -m second_mind.evaluation \
  data/sample_journals \
  data/sample_journals/retrieval_evaluation.json
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
- Conversational RAG, answer synthesis, or an LLM interface.
- Real or private journal evaluation and broader refusal-policy work.
- Knowledge graphs, summarization, reranking, hybrid search, background
  watchers, or filesystem automation.
