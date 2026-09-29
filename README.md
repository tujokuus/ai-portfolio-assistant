# AI Portfolio Assistant

A portfolio project built incrementally toward a locally running, evidence-grounded
assistant. **Only Phase 1 is implemented:** UTF-8 Markdown/text loading and
deterministic chunking. There is no search, model, API, or UI yet.

## Setup (PowerShell)

Run these commands from the repository root with Python 3.11 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m backend.ingestion
```

No environment activation is required. Runtime code uses only the standard
library. Installation needs access to Python package dependencies; ingestion and
tests run locally without external services. No environment variables or `.env`
file are needed in this phase.

## Manual ingestion preview

The three `data/example_*` documents are **fictional demonstration content** and
make no claims about Tuomas. Remove/replace them before using a real portfolio.
Add verified `.md` or `.txt` files in UTF-8 to `data/`, then run:

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
data/             Clearly labelled synthetic sample documents
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
and [phase instructions](docs/phase-instructions.md). Later phases will add
retrieval evaluation before generation, explicit index rebuilding, grounded
answers with traceable citations, and a separate API/UI. None is implemented yet.

Run the unit suite with `python -m pytest` using your configured environment.
Tests use synthetic temporary files and require no model downloads or services.

