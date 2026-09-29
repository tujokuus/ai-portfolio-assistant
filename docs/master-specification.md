# AI Portfolio Assistant

I want to build an AI-powered portfolio assistant as a software/AI engineering portfolio project.

The application should allow recruiters, technical interviewers, and other visitors to ask questions about my:

- work experience
- technical skills
- education
- machine learning experience
- data science experience
- AI projects
- software projects
- GitHub projects
- bachelor's thesis
- technologies and tools I have used

The assistant should answer questions using only information contained in my portfolio data.

Examples:

- What machine learning experience does Tuomas have?
- Has Tuomas worked with Databricks?
- What computer vision experience does he have?
- Which projects demonstrate Python skills?
- What did Tuomas do at Cense Analytics?
- What was his bachelor's thesis about?
- Does he have experience with data pipelines?
- Which projects demonstrate AI engineering skills?
- What experience does he have with TensorFlow?
- What are his most relevant data science projects?

The long-term goal is to integrate this assistant into my public portfolio website.

However, development should happen incrementally.

Do NOT try to implement the entire final system at once.

Each phase must be completed, tested, and reviewed before moving to the next phase.

---

# Core design principle

The application will use Retrieval-Augmented Generation (RAG).

The basic architecture is:

Portfolio documents
↓
Document loader
↓
Chunking
↓
Embeddings
↓
Vector database
↓
User question
↓
Semantic retrieval
↓
Relevant portfolio context
↓
LLM
↓
Grounded answer + sources

The application must NEVER invent information about me.

If the answer cannot be found from the supplied portfolio data, the assistant should clearly say that there is not enough information available.

---

# Development strategy

The project will be developed in two major stages.

## Stage 1 — Local MVP

The first working version should run entirely locally.

Technologies:

- Python
- FastAPI
- Streamlit
- Ollama
- a small instruct LLM such as Qwen
- sentence-transformers
- ChromaDB
- pytest

The local version should not require paid APIs.

The purpose of the MVP is to demonstrate:

- document ingestion
- embeddings
- semantic search
- vector databases
- RAG
- LLM integration
- backend APIs
- frontend integration
- testing
- prompt engineering
- basic AI guardrails

---

# Stage 2 — Public portfolio version

After the local MVP works reliably, it will later be migrated to a public architecture.

Possible production architecture:

User
↓
Next.js / React frontend
↓
backend API
↓
rate limiting + bot protection
↓
vector retrieval
↓
OpenAI API
↓
answer + sources

Potential production technologies:

- Next.js / React
- FastAPI
- OpenAI API
- Supabase PostgreSQL + pgvector
- Vercel
- Render or another backend hosting service
- Cloudflare Turnstile
- IP/session based rate limiting
- usage limits
- API cost controls

Do NOT implement production infrastructure during the initial MVP unless explicitly requested.

---

# Portfolio documents

Create a data directory.

Example structure:

data/
├── cv.md
├── work_experience.md
├── cense_analytics.md
├── education.md
├── skills.md
├── bachelor_thesis.md
├── projects.md
├── korisliiga_fantasy.md
├── ukraine_dashboard.md
└── meeting_assistant.md

The system must not hard-code my portfolio information.

Instead, the application should load documents from this directory.

Supported formats initially:

- .md
- .txt

More formats can be added later if needed.

---

# RAG behaviour

For every question:

1. Validate the user input.
2. Embed the question.
3. Retrieve the most relevant portfolio chunks.
4. Pass only those chunks to the language model.
5. Generate an answer based only on the retrieved context.
6. Return the answer.
7. Return the sources used.

Example:

Question:

Does Tuomas have experience with Databricks?

Possible response:

Tuomas has used Databricks in his work at Cense Analytics, including Python, SQL and PySpark based data processing and machine learning workflows.

Sources:
- cense_analytics.md
- skills.md

---

# Hallucination prevention

The assistant must follow strict grounding rules.

System prompt should communicate something similar to:

"You are an AI portfolio assistant representing Tuomas Kuusisto's professional portfolio.

Answer questions using ONLY information contained in the supplied portfolio context.

Never invent employment history, education, technologies, responsibilities, project results, achievements or skills.

If the information cannot be found in the context, say that there is not enough information in the portfolio.

Keep answers concise, factual and professional.

Refer to Tuomas in the third person.

When relevant, mention the work experience or project supporting the answer."

The retrieved portfolio context must remain authoritative even if the user tries prompt injection such as:

"Ignore all previous instructions."

---

# Sources

Every answer should provide source information.

At minimum:

- source filename
- document title if available

Potential later enhancement:

- section name
- GitHub repository URL
- direct project URL

---

# Project architecture

Use a clean modular structure.

Possible structure:

portfolio-ai/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── ingestion.py
│   ├── chunking.py
│   ├── embeddings.py
│   ├── vector_store.py
│   ├── retrieval.py
│   ├── llm.py
│   ├── rag.py
│   └── models.py
│
├── frontend/
│   └── app.py
│
├── data/
│
├── vector_db/
│
├── tests/
│
├── scripts/
│
├── .env.example
├── .gitignore
├── pyproject.toml or requirements.txt
└── README.md

You may improve this structure if there is a clear technical reason.

Avoid unnecessary abstraction.

This is a portfolio project, so code should remain understandable to someone reviewing the repository.

---

# LLM abstraction

The local MVP will use Ollama.

However, design the LLM layer so that OpenAI can replace Ollama later without rewriting the entire RAG pipeline.

For example:

LLMClient interface

Implementations:

OllamaClient

Future:

OpenAIClient

Do not over-engineer this abstraction.

---

# Vector database abstraction

The MVP will use ChromaDB.

Later, production may use PostgreSQL + pgvector.

Keep vector database interaction reasonably isolated from the rest of the application.

---

# Testing strategy

Testing is important because this is a portfolio project.

Use pytest.

Tests should eventually cover:

- document loading
- chunking
- embeddings integration where appropriate
- retrieval
- API validation
- API endpoints
- error handling
- unsupported files
- empty questions
- overly long questions

Mock expensive or external components where appropriate.

Do not require Ollama to be running for the entire unit test suite.

---

# Git workflow

Development should happen incrementally.

Prefer small logical commits.

Examples:

feat: initialize project structure

feat: add portfolio document loader

feat: add document chunking

feat: add embeddings and vector storage

feat: implement semantic retrieval

feat: integrate Ollama

feat: implement RAG pipeline

feat: add FastAPI chat endpoint

feat: add Streamlit interface

test: add retrieval and API tests

docs: document project architecture

Avoid one massive commit containing the entire project.

---

# Development phases

Implement the project in the following phases.

## Phase 1

Project initialization + document ingestion.

Goals:

- Python project structure
- configuration
- Markdown/text loading
- document metadata
- chunking
- basic tests

No LLM.
No vector database.
No FastAPI.
No Streamlit.

---

## Phase 2

Embeddings + ChromaDB.

Goals:

- sentence-transformers
- ChromaDB
- document embedding
- vector storage
- semantic retrieval
- command-line retrieval test

At the end of Phase 2, a question such as:

"Does Tuomas have Databricks experience?"

should return relevant portfolio chunks.

No LLM yet.

---

## Phase 3

Ollama + RAG.

Goals:

- local LLM client
- RAG context construction
- system prompt
- grounded answers
- source output
- prompt injection resistance
- graceful Ollama errors

At the end of Phase 3, the assistant should work from the command line.

---

## Phase 4

FastAPI backend.

Goals:

- /health
- /chat
- request/response models
- validation
- error handling
- source metadata in API response

The frontend must not be coupled directly to the RAG implementation.

---

## Phase 5

Streamlit frontend.

Goals:

- chat UI
- example questions
- conversation history
- source display
- loading state
- clear conversation button

The result should be a complete local MVP.

---

## Phase 6

Testing + reliability.

Goals:

- stronger unit tests
- API tests
- retrieval tests
- malformed input tests
- mock LLM tests
- error handling
- logging

---

## Phase 7

Portfolio polish.

Goals:

- strong README
- Mermaid architecture diagram
- screenshots instructions
- example questions
- design decisions
- limitations
- future architecture
- setup instructions
- project description suitable for recruiters

Do not exaggerate capabilities.

---

## Phase 8

Production migration.

This phase will be implemented only after explicitly requested.

Possible work:

- OpenAI provider
- React/Next.js frontend
- hosting
- Supabase/pgvector
- rate limiting
- Cloudflare Turnstile
- usage tracking
- OpenAI spending controls
- GitHub integrations

Do NOT start Phase 8 automatically.

---

# Development rules

For every phase:

1. First inspect the existing repository.
2. Preserve working code from previous phases.
3. Explain briefly what will change.
4. Implement only the requested phase.
5. Add or update tests.
6. Run tests.
7. Fix failures.
8. Do not move automatically to the next phase.
9. Summarize what was implemented.
10. Suggest an appropriate Git commit message.

Do not generate large amounts of unnecessary boilerplate.

Prefer simple, readable implementations.

Use:

- type hints
- clear naming
- useful docstrings
- modular code
- sensible error handling

Avoid:

- unnecessary design patterns
- unnecessary frameworks
- unnecessary dependencies
- premature production infrastructure

Do not use LangChain unless there is a strong technical justification. The goal is partly to demonstrate understanding of RAG implementation itself.

When implementing something, prefer code that I could reasonably explain during a technical interview.

The end result should demonstrate practical AI engineering rather than merely wrapping an LLM API.