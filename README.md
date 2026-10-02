# AI Portfolio Assistant

**Selected design:** full-context answering with OpenAI for the first application
version. See [the architecture decision and measured comparison](ARCHITECTURE_DECISION.md)
for the three approaches explored, answer-quality findings, timings, costs and
limitations. Full context sends the complete curated corpus; it does not run a
retrieval search. Local RAG and hosted File Search remain available for comparison.

`ask` and `compare` now default to `--mode full`. API use remains explicit through
`--provider openai`; omitting the provider still selects Ollama.

Next manual check: five questions covering earlier weak cases and unsupported
claims, using the selected full-context implementation:

```powershell
.\.venv\Scripts\python.exe -m backend.compare --provider openai --dataset tests/evaluation_full_followup.json --suite all --output reports/full-followup-01.json
```

Review factual support, source citations, useful completeness, appropriate
abstention and resistance to fabricated credentials before building the UI.
This follow-up has been prepared but not executed by the coding agent.

A portfolio project built incrementally toward a locally running, evidence-grounded
assistant. Phase 1 provides UTF-8 Markdown/text loading and deterministic chunking.
Phase 2 adds local multilingual embeddings, ChromaDB retrieval, and retrieval
evaluation. The user has run Phase 2 retrieval and its evaluation. Phase 3 adds
Ollama or OpenAI answers with either full portfolio context or retrieved chunks,
plus a comparison report. The user has evaluated the Ollama implementation.
The new OpenAI adapter and its offline tests have not been run by the coding agent,
at the user's request. There is no backend API or frontend yet.

## OpenAI: manual setup and comparison

### Full vs File Search: four-question experiment

`tests/evaluation_cloud_four.json` contains four English questions with expected
facts and sources: Databricks, a comparison of two projects, the false premise
about cross-session embeddings, and a chocolate cake recipe request. The shared
v4 prompt limits answers to the portfolio; the last request should produce a
brief scope explanation without a recipe or citations. References are never
sent to the model.

With `OPENAI_API_KEY` set, run these commands yourself:

```powershell
# File Search alone needs the optional official SDK.
.\.venv\Scripts\python.exe -m pip install -e ".[cloud]"

# Upload the Markdown/text portfolio snapshot once.
.\.venv\Scripts\python.exe -m backend.file_search upload

# Four questions, two modes: eight generation requests plus search tool calls.
.\.venv\Scripts\python.exe -m backend.compare --provider openai --mode cloud-both --dataset tests/evaluation_cloud_four.json --suite all --output reports/full-vs-file-search-01.json

# Optional individual question.
.\.venv\Scripts\python.exe -m backend.ask "What has Tuomas used Databricks for?" --provider openai --mode file-search

# Offline tests, to be run manually.
.\.venv\Scripts\python.exe -m pytest tests/test_file_search.py tests/test_openai.py tests/test_rag.py -q
```

`both` still means full vs local RAG; `cloud-both` means full vs hosted File Search.
Use a fresh report filename each run. Add `--limit 1` for a two-response smoke test;
omit it to include all four questions. File Search does not load local embeddings
or Chroma. It uses the Responses `file_search` tool and OpenAI's chunking/indexing.
The model may skip search for an unrelated question; tool counts are recorded.

Upload saves the store ID, file IDs and corpus hash to `vector_db/file-search.json`
(gitignored). Questions reuse that store rather than uploading again. Stale or
incomplete snapshots fail before generation. Remote file membership is also
checked; keep the experimental store immutable during a comparison. Reports save
retrieved snippets, tool queries, usage and validated citations. A cited file must
belong to the snapshot and appear in returned search results. This validates
identity, not semantic correctness. Full and File Search use the same core rules
with different evidence/citation instructions: this is an end-to-end comparison.

After changing documents, upload with `--manifest vector_db/file-search-v2.json`
and use `--file-search-manifest vector_db/file-search-v2.json` in ask/compare.
Existing manifests are never overwritten. Failed uploads preserve known resource
IDs; there is no automatic resume or deletion. Inspect OpenAI Platform Storage
before repeating a failed upload: a timeout can leave resources whose IDs were
not returned. The store expires seven days after last activity. Uploaded Files
API objects are separate: when finished, delete the experimental store and its
recorded uploaded files in Platform Storage. Removing the local manifest or using
`store=false` for answers does not delete the uploaded knowledge base.

File Search tool calls are billed in addition to tokens and possible storage.
The report includes cache-write tokens and tool counts, but is not an invoice.
Timings exclude upload and snapshot verification. No uploads, model calls, package
installation or tests were run during implementation.
See [File Search](https://developers.openai.com/api/docs/guides/tools-file-search)
and [vector stores](https://developers.openai.com/api/docs/guides/retrieval).

The existing CLI defaults to Ollama. Select `--provider openai` explicitly to send
portfolio evidence to OpenAI. Its default model is `gpt-6-luna`, with reasoning
effort `none`; override these with `--model` and `--reasoning-effort` when supported
by the selected model. Both providers now use the English-only v4 scope prompt.
The full/local RAG modes do not upload a hosted vector store. In `rag`
mode only the retrieved evidence is sent; `full` sends all portfolio documents.
Existing local embeddings and Chroma are unchanged. No re-indexing is needed.

The adapter uses Python's standard-library HTTPS client and needs no new package.
Set `OPENAI_API_KEY` in the process environment or deployment secret manager.
`.env.example` is a reference only; `.env` is not automatically loaded. Never commit
the key or include it in browser code. In PowerShell 7, read it without putting the
key itself in command history:

```powershell
$env:OPENAI_API_KEY = Read-Host "OpenAI API key" -MaskInput

# One paid request. Full mode needs no local retrieval dependencies/index.
.\.venv\Scripts\python.exe -m backend.ask "What has Tuomas used Databricks for?" --provider openai --mode full

# Eight English questions, both modes: up to 16 paid requests.
.\.venv\Scripts\python.exe -m backend.compare --provider openai --mode both --output reports/openai-english-v3-01.json

# Same English suite with Ollama, for a separate provider comparison.
.\.venv\Scripts\python.exe -m backend.compare --provider ollama --mode both --output reports/ollama-english-v3-01.json

# Offline checks you can run yourself; no API key, network or model is needed.
.\.venv\Scripts\python.exe -m pytest tests/test_openai.py tests/test_rag.py -q
```

Use a fresh output filename each time. `--limit 2` reduces a two-mode comparison
to four requests, but excludes the harder cases. The default dataset is
`tests/evaluation_smoke_en.json`; the original 30-question dataset is preserved.
English and Finnish runs are different experiments: question wording can change
retrieval, so compare providers on the same English dataset and prompt version.

The OpenAI request uses Responses API strict JSON Schema output, `store=false`,
standard processing and disabled truncation. No built-in tools or automatic
retries are enabled. Application citation/status checks still apply: structured
output does not prove factual correctness. The key is not stored in configuration
or reports. `store=false` does not mean zero retention under all API policies.
An API timeout may still incur charges; check usage before repeating a large run.

Each answer stores `metrics.usage`, the returned model, response ID and service
tier. The report's `summary` totals time, errors and reported token usage by mode,
including usage for generated answers rejected by validation. Missing usage is
not evidence of zero cost. Output tokens already include reasoning tokens; do not
add those twice. The `--num-ctx` value remains a conservative local input-budget
guard for OpenAI, not a request to change its model context window.

For ordinary token pricing, estimate USD as `(uncached input tokens * input rate
+ cached input tokens * cached rate + output tokens * output rate) / 1,000,000`.
Use rates for the returned model and processing tier, and account separately for
any cache-write, regional or other applicable charges. Reports contain measured
usage, not an invoice or hard-coded price estimate. On 2026-10-01, the documented
standard short-context GPT-6 Luna rates are $0.10 input, $0.01 cached input and
$0.50 output per million tokens; Batch/Flex rates are different. Our own retrieval
does not incur an OpenAI File Search tool fee. Hosting and taxes are separate.

Official references: [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna),
[Responses and text generation](https://developers.openai.com/api/docs/guides/text),
[structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

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
  llm.py          Provider protocol and Ollama HTTP client
  rag.py          Shared grounding, evidence, and answer validation
  ask.py          Single-question CLI (full or rag)
  compare.py      Two-mode answer comparison for manual review
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
and [phase instructions](docs/phase-instructions.md). Phase 3 provides grounded
answer generation and a full-context comparison; later phases add the separate
API/UI. Generation quality and guardrail effectiveness remain to be measured.

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

## Phase 3: local answers with full context or RAG

Both modes use the same selected provider/model, system instructions, JSON answer
schema and output limit. Ollama uses temperature 0 and seed 42; OpenAI uses the
configured reasoning effort without these Ollama options.
Both use `portfolio-grounding-v4-scope` automatically.
`full` (the CLI default) reads all nonempty portfolio documents. It does not need
Chroma, embeddings, or an index. `rag` uses the existing
top-k chunk search and refuses an index that differs from the current corpus.
Neither mode reads evaluation answers or review notes as portfolio evidence.
Each CLI invocation is independent; there is no conversational memory.

The initial model is [`qwen3:4b-instruct`](https://ollama.com/library/qwen3:4b-instruct),
a configurable starting point rather than a measured best choice for this machine.
The listed download is about 2.5 GB; runtime memory also includes the context cache
and other overhead. Hardware inspection was unavailable, so fit and speed have not
been established. The default context setting is 32,768 tokens; reduce it only if
your input still fits, or choose another model with `--model`.

Install [Ollama for Windows](https://ollama.com/download/windows) and start its app.
In PowerShell, run these commands yourself (none was run during implementation):

```powershell
# Download the model once. This requires internet access.
ollama pull qwen3:4b-instruct

# Inspect installed model tags/IDs; save the ID with comparison results.
ollama list

# Full portfolio: no index or additional Python runtime dependency is needed.
.\.venv\Scripts\python.exe -m backend.ask "Mitä kokemusta Tuomaksella on Databricksista?" --mode full

# RAG: uses the Phase 2 index you already built.
.\.venv\Scripts\python.exe -m backend.ask "Mitä kokemusta Tuomaksella on Databricksista?" --mode rag --top-k 5

# Inspect accepted statements, cited sources, full supplied context, and timings.
.\.venv\Scripts\python.exe -m backend.ask "Where has Tuomas used TensorFlow?" --mode full --json

# Unknown information should result in an explicit limitation, not a fabricated fact.
.\.venv\Scripts\python.exe -m backend.ask "Mitä AWS-sertifikaatteja Tuomaksella on?" --mode full

# Offline mocked tests, including HTTP error handling; no Ollama needed.
.\.venv\Scripts\python.exe -m pytest -q
```

If the desktop Ollama app is not running the server, run `ollama serve` in a
separate terminal and leave it open. Do not start a second server if the app already
listens on port 11434. The Python client never installs Ollama or pulls models.
Ollama generation uses `http://localhost:11434` by default. Setting `--ollama-url` to
another server sends the supplied portfolio context to that server.

Useful CLI options (also accepted by the comparison command):

| Option | Default | Purpose |
|---|---|---|
| `--model` | `qwen3:4b-instruct` | Installed Ollama model tag |
| `--timeout` | `180` | HTTP timeout in seconds; try 300 on a slow first run |
| `--num-ctx` | `32768` | Requested context window, subject to model/hardware support |
| `--max-output-tokens` | `1024` | Generation limit; incomplete output is an error |
| `--ollama-url` | `http://localhost:11434` | Ollama server |
| `--data-dir` | `data` | Portfolio source directory |
| `--db-dir` | `vector_db` | RAG index directory |
| `--top-k` | `5` | Retrieved chunks in RAG mode |

Question length is limited to 2,000 characters by `LLMConfig`. Configuration is
explicit, so no `.env` loader is required. The stdlib HTTP adapter uses Ollama's
[`/api/chat` structured output](https://docs.ollama.com/api/chat) with streaming off.
The default instruct model avoids relying on a thinking-mode toggle; other model
families may behave differently and must be verified before comparing them.

## Comparing full context and RAG

The default is eight curated questions using full context: eight generation requests.
They cover education, Databricks work, work/project synthesis, a misleading premise
about voice-agent retrieval, an undocumented thesis topic, undocumented AWS
certifications, unavailable employer result metrics, and a request to invent
credentials. References come from the existing evaluation dataset. Missing
documentation must not be interpreted as proof of missing experience.

```powershell
.\.venv\Scripts\python.exe -m backend.compare --output reports/answers-v3-smoke.json
```

Optional comparisons (not required for each prompt change):

```powershell
# Eight questions in both modes: 16 generation requests.
.\.venv\Scripts\python.exe -m backend.compare --mode both --output reports/answers-v3-both.json

# All 30 questions, full context: 30 generation requests.
.\.venv\Scripts\python.exe -m backend.compare --dataset tests/evaluation_queries.json --suite all --output reports/answers-v3-all.json

# Full original comparison: 60 generation requests.
.\.venv\Scripts\python.exe -m backend.compare --dataset tests/evaluation_queries.json --suite all --mode both --output reports/answers-v3-all-both.json
```

`--limit N` further limits the selected suite; small limits may omit the unknown
information and fabrication cases at the end. Use `--suite all` with custom
datasets that do not contain the curated smoke IDs. This small suite is a spot
check, not a comprehensive measurement of reliability.

Use a new output filename for each run; existing reports are not overwritten.
The command reads the corpus once, verifies that the RAG index matches when used,
alternates mode order when comparing both modes, and saves after each question.
An interruption can leave a report with status `running`; completed questions remain available. It is not
an automatic resume mechanism. Runtime errors are recorded separately from factual
abstentions, and a completed report with errors exits with code 1.

Inspect `cases[].results.full` (or `rag` / `file-search` when selected). Each contains
the answer, structured statements, cited sources, actual supplied evidence, wall
time, and provider usage/timing fields when returned. The report also records model
settings, prompt version, dataset/corpus hashes, and index configuration. The
`reference_for_manual_review_only` fields are added to the report after answering;
they are never included in model messages.

Fill in `manual_review` for each mode:

- Are all factual claims supported by the supplied context?
- Does the answer address the question and preserve important limitations?
- Does each cited source actually support the associated statement?
- Are missing information and misleading premises handled correctly?
- Does the answer use clear English, as required by the v4 prompt?
- Does it describe supported experience without implying that undocumented
  experience does not exist? A broad question about Databricks experience can be
  `answered` by documented work; it should not list unrequested certifications or
  repeat the answer in a limitation. Ask separately about certifications to check
  that genuinely missing requested information is still acknowledged.

Known reference-source restrictions can be too narrow (for example, education
facts also appear in the profile). Judge semantically and do not manufacture an
accuracy score from literal matching. The command intentionally does not call
another LLM to grade answers. First requests can include model/embedding loading;
later ones benefit from caches. Wall times are observations, not a controlled
speed benchmark; inspect `load_duration` and repeat if timing matters. Assistant
initialization/file loading is outside per-answer wall time.

## Grounding limits and failures

The model returns `answered`, `partial`, or `insufficient`. Each factual statement
must have known source IDs, which the application resolves and renders as `[S1]`.
An insufficient response has only a limitation, no factual statements. Partial
responses combine cited facts and a missing-information explanation. Only cited
evidence appears in the source list; the JSON separately exposes all supplied
context. IDs are per request, and RAG source entries retain section and chunk IDs.
Multiple chunks from one file may have separate IDs: this preserves exact evidence.

Invalid JSON, unknown citations, missing required fields, connection failures,
HTTP errors, timeout, and exhausted generation limits produce explicit failures,
not a fabricated answer or a misleading "no information" result. No-context
requests bypass the model and return a fixed insufficient-evidence message.

Context is guarded with a conservative UTF-8 byte-based estimate including the
schema, output allowance, and template margin. This is not an exact tokenizer
measurement and may reject inputs that would actually fit. It never silently drops
documents to make `full` fit. Ollama's returned prompt count is checked when present;
model/server context handling still needs manual verification. Increasing context
or output limits increases resource requirements.

Evidence is encoded as data in a JSON message, separated from system instructions.
This and strict citation validation reduce some failure modes, but do not guarantee
injection resistance, truthful abstention, or semantic support of every claim.
Mocked tests check implementation contracts, not real model reliability. Neither
mode can establish that an unknown fact is absent from Tuomas's real experience.
No tools, browsing, history, FastAPI, or frontend are provided to the answering model.

