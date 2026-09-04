# Second Mind

Second Mind is a local-first personal knowledge system for turning typed journal
entries into grounded answers with dates and source citations.

## Current status

The January method-formation milestone adds an opt-in, privacy-safe way to log
real-use outcomes and rank recurring failure categories. The local log stores
only a timestamp and one fixed category; it has no field for journal content,
questions, answers, citations, source paths, or free-form notes.

## Quick start

Refresh the local index and ask one or more questions in the same command:

```bash
python -m second_mind data/sample_journals \
  --question "What reserved book did I pick up?" \
  --question "Which mountain trail did I hike?"
```

The command indexes new or changed journal chunks, skips unchanged chunks on
later runs, returns the top supporting passage unchanged as a conservative
grounded answer, and prints its date/source/title/chunk citation. A question
without supporting evidence prints an explicit refusal and still exits
successfully because refusing is expected MVP behavior. Use `--index PATH` for
a separate local SQLite index; the default remains
`data/indexes/journals.sqlite3`.

After installing the editable project, the same workflow is available as:

```bash
second-mind data/sample_journals \
  --question "What reserved book did I pick up?"
```

## Local backups

First refresh the index with the normal MVP command. Then create a timestamped
snapshot in a local directory or mounted external drive that you choose:

```bash
python -m second_mind.backup create \
  data/sample_journals /path/to/local/backups \
  --index data/indexes/journals.sqlite3
```

The command copies the journal directory and current SQLite index, writes a
manifest containing relative paths, sizes, and SHA-256 checksums, verifies the
new snapshot, and reports only counts and paths. It never overwrites an existing
snapshot. Use `--name NAME` when a stable unique snapshot name is useful for an
automated local workflow.

Verify any snapshot again without reading journal text into the console:

```bash
python -m second_mind.backup verify \
  /path/to/local/backups/second-mind-YYYYMMDDTHHMMSSZ
```

After editable installation, `second-mind-backup` provides the same `create`
and `verify` subcommands. Store real-journal snapshots only on a trusted local
or encrypted external volume. Full restore automation and a clean restore
rehearsal remain intentionally deferred to M059.

## Privacy-safe usage evidence

After each real use, record exactly one outcome category without copying the
question, answer, citation, journal text, filename, title, or personal notes:

```bash
python -m second_mind.usage categories

python -m second_mind.usage record correct-answer
python -m second_mind.usage record wrong-passage
python -m second_mind.usage record incorrect-refusal
```

The default log is `data/usage/outcomes.jsonl`, which Git ignores. You can use
`--log PATH` before the subcommand to choose another local file. The record
format is intentionally strict and rejects extra or free-form fields.

Check progress and rank up to three recurring failure categories:

```bash
python -m second_mind.usage report
```

The report shows how many of the ten required uses remain and prints provisional
failure rankings while evidence is still accumulating. Once ten real uses
exist, it marks the evidence ready; the three most frequent failure categories
are then the milestone priorities. After editable installation, the same
commands are available through `second-mind-usage`.

## Component commands

The lower-level commands remain available for inspection and diagnostics. The
public Markdown loading functions are:

```python
load_journal(path: Path) -> JournalEntry
load_journals(directory: Path) -> list[JournalEntry]
```

`load_journal` validates and loads one journal. `load_journals` ignores
non-Markdown files, warns and continues when a Markdown journal is invalid, and
returns valid entries in chronological order.

Loaded bodies can now be divided into deterministic, overlapping chunks. Each
chunk retains its journal date, source path, optional title, and source-local
chunk index. A dependency-free feature-hashing backend embeds the chunks
locally, and a SQLite index persists their text, vectors, and metadata under
the gitignored `data/indexes/` directory. Re-indexing unchanged source chunks
skips them instead of creating duplicates.

Inspect what the directory loader parsed:

```bash
python -m second_mind.ingest data/sample_journals
```

The command prints each valid entry's date, optional title, source filename, and
body character count in chronological order. Validation warnings remain on
standard error. It exits successfully when at least one valid entry loads, and
exits with status 1 for an invalid directory or when no valid entries load.

Index the synthetic sample journals using the default local index:

```bash
python -m second_mind.index data/sample_journals
```

Query the index and return the three closest chunks with citation metadata:

```bash
python -m second_mind.index --query library
```

Use `--index PATH` on either command to select another SQLite file. Indexing
also accepts `--chunk-size` and `--overlap`; both are measured in characters.
Querying accepts `--limit`.

Ask a natural-language question and return only evidence-positive passages with
explicit journal date, source filename, optional title, and chunk citations:

```bash
python -m second_mind.retrieval \
  "What book did I pick up at the library?"
```

The retrieval command accepts `--index`, `--limit`, and `--minimum-score`. It
ignores common question words and requires an informative term to overlap the
source text, preventing feature-hash collisions from surfacing unsupported
passages. It exits with status 1 instead of returning zero-evidence passages.
The retrieval component returns cited source text only. The stabilized MVP
workflow uses the top passage unchanged as its answer; it does not perform
abstractive synthesis.

Run the committed privacy-safe scorecard against the fictional sample journals:

```bash
python -m second_mind.evaluation \
  data/sample_journals \
  data/sample_journals/retrieval_evaluation.json
```

The evaluator creates a fresh temporary index, runs exactly five questions, and
scores top-passage retrieval, source/date/title/chunk citation metadata, and an
insufficient-evidence refusal. It exits with status 1 if any applicable check
fails. The committed scorecard contains four evidence-positive questions and
one refusal question; it never requires private journal content.

## MVP v0.1 capabilities

The local MVP can:

- Ingest local typed journal files.
- Automatically chunk, embed, and index entries.
- Accept natural-language questions.
- Retrieve relevant journal passages.
- Return conservative extractive answers grounded in retrieved passages.
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
- Embedding, persistence, and querying run locally without cloud services,
  telemetry, hosted APIs, or journal-data transmission.

## Handwritten imports

Handwritten pages use a deliberate local workflow. Scan a page with the iPhone
document scanner, transfer it locally to the active Mac, then create a draft
with the handwritten-import command. macOS Vision runs on-device; the original
scan, private state, and editable draft remain in the ignored
`handwritten_import/` workspace.

Review and correct the draft before explicitly approving it. Approval writes a
normal dated Markdown journal entry but does not refresh the index. Run the
existing index command afterward when you decide the approved entry should be
searchable. This first version has no background watcher, cloud fallback,
automatic cleanup, or phone-to-computer synchronization.

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
data/indexes/           Ignored local SQLite indexes
data/usage/             Ignored non-sensitive local outcome records
handwritten_import/     Ignored local scan, draft, and import-state workspace
src/second_mind/        Ingestion, retrieval, backup logic, and CLIs
tests/                  Foundation, ingestion, sample-contract, and CLI tests
```

## Current non-goals

This milestone does not include automatic or background usage tracking,
question/answer logging, source-path logging, free-form notes, journal-content
inspection, restore automation, a clean restore rehearsal, scheduled backups,
cloud storage, encryption or key management, conversational RAG, abstractive
answer synthesis, an LLM interface, agents, a web UI or framework, model
downloads, semantic reranking, hybrid search, OCR, or handwritten notes. The
feature-hashing vectors provide deliberately small lexical retrieval for
milestone verification; the isolated embedding interface allows a future local
semantic model to replace them.
