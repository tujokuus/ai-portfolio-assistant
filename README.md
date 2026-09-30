# AI Portfolio Assistant

A portfolio project built incrementally toward a locally running, evidence-grounded
assistant. Phase 1 provides UTF-8 Markdown/text loading and deterministic chunking.
Phase 2 adds local multilingual embeddings, ChromaDB retrieval, and retrieval
evaluation. **Phase 2 code has not been executed or tested yet**, at the user's
request. There is no generative LLM, backend API, or frontend yet.

## Setup (PowerShell)

Run these commands from the repository root with Python 3.11 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,retrieval]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m backend.ingestion
```

No environment activation is required. Python 3.12 is the recommended starting
environment for this repository. If `.venv` already exists, skip its creation.
Phase 1 uses only the standard library; Phase 2 uses the optional `retrieval`
dependencies. Installation and the initial embedding-model download need internet
access. No paid APIs, API keys, or `.env` file are needed. The commands shown here
are instructions for manual verification, not evidence of successful execution.

## Manual ingestion preview

The fictional sample documents have been removed. Add verified `.md` or `.txt`
files in UTF-8 to `data/`, then run:

```powershell
.\.venv\Scripts\python.exe -m backend.ingestion --data-dir data --chunk-size 600 --chunk-overlap 80
```

Output is JSON containing document/chunk counts, chunking configuration, and each
chunk's text, source path, title, section, zero-based index, and SHA-256 ID. Inspect
these fields to verify that your text and source evidence are preserved. An
installed `portfolio-ingest` command provides the same CLI. Paths are relative to
the current working directory, so use an absolute `--data-dir` outside the repo.

Files are scanned recursively in sorted order. Relative source paths distinguish
files with the same name in different subdirectories. Unsupported files and
symlinks are skipped; explicitly loading an unsupported file raises `ValueError`.
Unreadable or invalid UTF-8 files stop ingestion with an explanatory error rather
than silently creating an incomplete result. An empty directory yields zero
documents/chunks; whitespace-only documents are counted but produce no chunks.

## Structure

```text
backend/
  config.py       Validated ingestion settings
  models.py       Immutable Document and DocumentChunk dataclasses
  ingestion.py    File loading and JSON preview CLI
  markdown.py     Shared Markdown heading scanner
  chunking.py     Section splitting and overlapping character windows
  embeddings.py   Local sentence-transformers adapter and input limits
  vector_store.py Chroma persistence and result conversion
  indexing.py     Explicit rebuild and active-index manifest
  retrieval.py    Semantic search service and CLI
  evaluation.py   Source-recall evaluation and JSON reports
data/             Curated portfolio documents only
tests/            Loader, chunking, configuration, and CLI tests
docs/             Original specifications and accepted design decisions
pyproject.toml    Packaging and pytest development dependency
```

Python callers can use the same functions without the CLI:

```python
from pathlib import Path
from backend.config import IngestionConfig
from backend.ingestion import load_documents
from backend.chunking import chunk_document

config = IngestionConfig(data_dir=Path("data"), chunk_size=1000, chunk_overlap=150)
chunks = [
    chunk
    for document in load_documents(config.data_dir)
    for chunk in chunk_document(document, config)
]
```

## How chunking works

Markdown ATX headings (`#` through `######`) start sections. Each chunk retains
the full heading hierarchy in its `section` metadata; headings inside fenced code
blocks are ignored. The first nonempty H1 is the document title, falling back to
the filename stem. Plain text uses the filename stem and has no sections.

Sections are split into windows of at most **1,000 Unicode characters** by default,
with **150 characters of overlap** within a section. Boundaries prefer whitespace
in the latter half of a window; long unbroken strings use a hard character split.
Whitespace at chunk edges is trimmed, so visible overlap may be shorter. Overlap
never crosses sections. Small sections remain small rather than being merged.
Continuation chunks retain section metadata even when the heading is not in their
text. A later context builder should include title/section alongside chunk text.

IDs are deterministic hashes of source, title, section, document-wide chunk index,
text, chunking version, and size/overlap settings. Repeated runs with unchanged
inputs produce the same IDs; edits or configuration changes can change IDs.
They are reproducible evidence identifiers, not permanent IDs across document edits.

This is intentionally a small Markdown scanner, not a complete parser. Setext
headings, HTML, and headings nested inside lists/blockquotes are not interpreted.
Long code blocks and tables can be split. Character limits are not token limits;
model-specific limits must be considered when embeddings are introduced.

## Content and future phases

Prefer one primary document per role/project, documenting individual contribution,
actual technologies, dates, and supported outcomes. Distinguish professional work,
coursework, and personal projects. Include only material intended for public use.
Example answers in specifications are illustrative and must not become facts.

See [accepted decisions](docs/design-decisions.md), the [master specification](docs/master-specification.md),
and [phase instructions](docs/phase-instructions.md). Later phases will add grounded
answers with traceable citations and a separate API/UI. Phase 3 should also compare
retrieved context against providing the full portfolio to the same local model.

Run the unit suite with `python -m pytest` using your configured environment.
Loader tests use synthetic temporary files; evaluation integrity checks read the
curated portfolio documents. Neither requires model downloads or services.

## Evaluation dataset

[tests/evaluation_queries.json](tests/evaluation_queries.json) contains 30 questions
with expected facts, source sections, verbatim evidence, and unsupported claims to
avoid. See [the evaluation guide](tests/EVALUATION.md) for scoring guidance and the
distinction between retrieval evaluation and generated-answer evaluation. Dataset
integrity checks and a retrieval evaluation command are available; answer
evaluation belongs to Phase 3. Keep evaluation files outside `data/`.

## Phase 2 manual walkthrough

Run from the repository root after installing `.[dev,retrieval]` above:

```powershell
# Build/rebuild the index. First use downloads the embedding model.
.\.venv\Scripts\python.exe -m backend.indexing

# Ask in Finnish or English; inspect the returned text and sources.
.\.venv\Scripts\python.exe -m backend.retrieval "Mitä kokemusta Tuomaksella on Databricksista?" --top-k 5
.\.venv\Scripts\python.exe -m backend.retrieval "What computer vision experience does Tuomas have?" --top-k 3

# Machine-readable results include full chunk IDs and metadata.
.\.venv\Scripts\python.exe -m backend.retrieval "Databricks experience" --json

# Evaluate the 30 questions and save the detailed results for inspection.
.\.venv\Scripts\python.exe -m backend.evaluation --top-k 5 --output reports/retrieval.json

# Run tests yourself; no model downloads are required by the test suite.
.\.venv\Scripts\python.exe -m pytest -q
```

Search prints rank, cosine distance, source, title, section, chunk index/ID, and
text. Smaller distances mean closer vectors; they are not confidence percentages
or evidence that a question can be answered. `top_k` counts chunks, not distinct
documents. Several chunks may come from the same source. There is no relevance
threshold or answerability decision yet: even unknown questions can return hits.

To change chunking, model, or documents, rerun indexing explicitly:

```powershell
.\.venv\Scripts\python.exe -m backend.indexing --data-dir data --db-dir vector_db --chunk-size 600 --chunk-overlap 80
```

The index is stored in `vector_db/`, with configuration, corpus fingerprint, counts,
timestamp, and active collection in `active.json`. Search uses the saved embedding
configuration automatically; it never re-embeds documents. Evaluation refuses a
stale index if current documents differ. Ordinary search uses the last snapshot
and does not scan for edits: rebuild after adding, changing, or deleting files.
An empty corpus deliberately publishes an empty index, removing old search hits.

Rebuilds publish a fresh collection only after successful writes. Old collections
are retained so a running search can finish against its snapshot. This increases
disk use over repeated rebuilds; automatic garbage collection is not implemented.
Interrupted builds may also leave an unused collection. Do not run concurrent
rebuilds; this MVP assumes one indexing process. Missing indexes produce a clear
error; an existing empty index returns no results without loading the model.

## Embedding choice and limits

Default: [`intfloat/multilingual-e5-small`](https://huggingface.co/intfloat/multilingual-e5-small).
It is a multilingual retrieval model selected for Finnish questions over English
documents. We use sentence-transformers on CPU, E5's `query: ` and `passage: `
prefixes (also for Finnish), and normalized embeddings. Document titles and section
paths are included in embedding inputs to preserve context. Original chunk text
and metadata remain separately inspectable. The model's documented limit is 512
tokens: the adapter checks token counts including prefixes/headings and rejects
overlong input instead of silently truncating it. Reduce chunk size or shorten
the question/headings if that happens.

Model name, revision, batch size, and prefixes are configurable on the index CLI
(`--model`, `--revision`, `--batch-size`, `--query-prefix`, `--passage-prefix`).
Defaults target E5: configure appropriate prefixes when trying another model.
Use an immutable Hugging Face commit SHA with `--revision` for reproducible model
weights. The convenient default `main` is recorded but is a moving reference;
weights are not guaranteed identical across separate downloads. Rebuild when
changing weights, prefixes, or chunking. Dependencies use version ranges and are
not yet locked to a verified environment because installation/testing is pending.

Chroma uses local persistence and explicitly supplied vectors (its default
embedding model is disabled). The collection uses
[cosine distance](https://docs.trychroma.com/docs/collections/configure).
Documents and queries are embedded locally; first-use model files come from
Hugging Face. Chroma anonymized telemetry is disabled in client settings.
For offline use after caching the model, set `HF_HUB_OFFLINE=1` in your environment.

The test suite uses fake embeddings for workflow tests. A real Chroma integration
test checks persistence, ordering, distances, and metadata with fixed vectors;
it is skipped if Chroma is not installed. Neither proves multilingual retrieval
quality: use the evaluation command and manually review its retrieved evidence.

