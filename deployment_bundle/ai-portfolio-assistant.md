# AI Portfolio Assistant

A source-grounded chatbot for exploring Tuomas Kuusisto's experience, education,
and software projects. Visitors can ask questions, read cited source text, and
open the original CV or project README.

**Status:** deployed on Render, with ongoing development and evaluation.

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

## Technical implementation

**Request flow.** The browser sends JSON to `POST /api/chat`. FastAPI and Pydantic
validate the question, including its 2,000-character limit. The backend combines
the question with the source snapshot and grounding instructions, then calls the
OpenAI Responses API over HTTPS using Python's standard-library HTTP client.
A strict JSON schema requests an answer status, factual statements, source IDs,
and any relevant information gaps. Application checks validate the response
structure and cited IDs before displaying the answer. There are no automatic
paid retries. `GET /health` checks service availability without calling a model.

**Sources and safeguards.** The backend assigns source IDs and renders citation
markers from validated references. Each cited document can be expanded as text
or opened through `GET /api/sources/{name}`, which serves only explicitly listed
source snapshots. Browser output is rendered as text rather than executable HTML.
The API key is read from a server environment variable. Host and browser-origin
checks, one concurrent generation, a chat switch, and shared rolling request
quotas limit use; origin checks are not user authentication. Quotas are held in
memory and reset on restart.

**Testing and delivery.** Pytest tests cover source loading, answer validation,
mocked provider failures, web routes, and request limits without real model calls.
Separate evaluation runs record answers, source evidence, corpus hashes, latency,
and token usage for manual factual review. Render runs FastAPI with Uvicorn from
a GitHub-linked repository. Code and source updates reach the service through
commits and deployment. The cloud reads `deployment_bundle/sources.json`; updating
a local CV or another project's README also requires refreshing its bundled copy.
Restarting the deployed service loads that release's source snapshot into memory.

## Engineering work

- Compared full context, local RAG (multilingual embeddings and Chroma), and
  OpenAI File Search before choosing full context for the initial application.
- Added repeatable question sets, manual review, corpus hashes, token reporting,
  timing measurements, and comparisons between original sources and summaries.
- Replaced manually maintained summaries in the browser with original documents.
- Built source inspection, keyboard controls, loading states, and error handling
  without a frontend framework or build step.
- Deployed the frontend and backend together on Render with configurable sources, one concurrent
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

These linked documents provide further detail for readers. The chatbot does not
automatically follow documentation links; only its explicitly listed sources are
included in model context.

- [Usage and earlier experiments](USAGE.md): local setup, CLI commands, RAG and File Search.
- [Evaluation](EVALUATION.md): offline tests and paid answer comparisons.
- [Deployment](DEPLOYMENT.md): source packaging, Render setup and release checks.
- [Architecture decision](ARCHITECTURE_DECISION.md): measured tradeoffs and limitations.

## Limits

Answers can be incomplete or wrong. PDF extraction needs review for complex
layouts. READMEs describe documented behavior rather than verified code execution.
There is no conversation memory, account system, persistent analytics, or code
search. Deployment quotas reset on restart and are not a billing guarantee.
