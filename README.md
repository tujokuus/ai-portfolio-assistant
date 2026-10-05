# AI Portfolio Assistant

A source-grounded chatbot for exploring Tuomas Kuusisto's experience, education,
and software projects. Visitors can ask questions, read cited source text, and
open the original CV or project README.

**Status:** locally tested prototype; public deployment preparation is in progress.
The latest deployment changes still require testing.

## How it works

```text
Browser chat → FastAPI → portfolio evidence + question → OpenAI
             ← validated answer and source references ←
```

The frontend uses plain HTML, CSS, and JavaScript. The Python backend loads an
explicit list of PDF and Markdown files at startup. PDF text is extracted with
pypdf; READMEs are used without AI summarization. The API key stays on the server.
Questions are independent; visible chat history is not model memory.

The current application uses **full context**: the complete selected source set
is sent with each question. It does not train or fine-tune the model. Structured
output and citation-ID checks reject malformed responses but do not prove that
claims are factually supported. Document contents are evidence, not instructions.

## Engineering work

- Compared full context, local RAG (multilingual embeddings and Chroma), and
  OpenAI File Search before choosing full context for the initial application.
- Added repeatable question sets, manual review, corpus hashes, token reporting,
  timing measurements, and comparisons between original sources and summaries.
- Replaced manually maintained summaries in the browser with original documents.
- Built source inspection, keyboard controls, loading states, and error handling
  without a frontend framework or build step.
- Prepared single-service Render hosting, configurable sources, one concurrent
  generation, a chat switch, and process-local request quotas.

Small initial experiments favored full context for this corpus. Newer originals
answered questions missing from older summaries, but used more input tokens.
Source freshness and coverage differed; these observations do not establish a
universally best architecture. See [the decision record](ARCHITECTURE_DECISION.md).

## Run locally

Requires Python 3.11+ and an OpenAI API key. From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[web,dev]"
# On a fresh checkout, copy sources.example.json to sources.local.json and edit paths.
$env:OPENAI_API_KEY = Read-Host "OpenAI API key" -MaskInput
.\.venv\Scripts\python.exe -m backend.web
```

Open http://127.0.0.1:8000. Sending a question makes a paid API request.
The current model is `gpt-6-luna`. Restart after updating your source documents.

## Documentation

- [Usage and earlier experiments](USAGE.md): local setup, CLI commands, RAG and File Search.
- [Evaluation](EVALUATION.md): offline tests and paid answer comparisons.
- [Deployment](DEPLOYMENT.md): source packaging, Render setup and release checks.
- [Architecture decision](ARCHITECTURE_DECISION.md): measured tradeoffs and limitations.

## Limits

Answers can be incomplete or wrong. PDF extraction needs review for complex
layouts. READMEs describe documented behavior rather than verified code execution.
There is no conversation memory, account system, persistent analytics, or code
search. Deployment quotas reset on restart and are not a billing guarantee.
