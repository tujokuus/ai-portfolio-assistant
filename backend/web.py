"""Local web interface: run with python -m backend.web from the repository."""

from contextlib import asynccontextmanager
import os
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.config import LLMConfig
from backend.llm import LLMError, create_client
from backend.rag import PortfolioAssistant, build_messages, Evidence
from backend.source_documents import load_source_documents
from backend.web_limits import RequestQuota

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
PUBLIC_ORIGIN = os.environ.get("PUBLIC_ORIGIN", os.environ.get("RENDER_EXTERNAL_URL", "")).rstrip("/")
if PUBLIC_ORIGIN and (urlsplit(PUBLIC_ORIGIN).scheme != "https" or not urlsplit(PUBLIC_ORIGIN).hostname
                      or urlsplit(PUBLIC_ORIGIN).path or urlsplit(PUBLIC_ORIGIN).query
                      or urlsplit(PUBLIC_ORIGIN).fragment or urlsplit(PUBLIC_ORIGIN).username):
    raise ValueError("PUBLIC_ORIGIN must be an HTTPS origin with no path or credentials")
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
if PUBLIC_ORIGIN:
    ALLOWED_HOSTS.append(urlsplit(PUBLIC_ORIGIN).hostname)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Snapshot the originals once, so displayed files match the model's evidence.
    # This is an application input budget, not a claim about the model's window.
    config = LLMConfig(provider="openai", model="gpt-6-luna", timeout_seconds=60,
                       num_ctx=131072)
    sources = load_source_documents(ROOT / os.environ.get("SOURCES_MANIFEST", "sources.local.json"))
    documents = [source.document for source in sources]
    app.state.originals = {source.document.source: source for source in sources}
    # Fail at startup if the full corpus cannot fit; never silently drop a README.
    build_messages("?" * config.max_question_chars, [
        Evidence(f"S{index}", doc.source, doc.title, None, None, doc.text)
        for index, doc in enumerate(documents, 1)
    ], config)
    app.state.assistant = PortfolioAssistant(
        create_client(config), config, mode="full", documents=documents
    )
    app.state.generation_lock = Lock()
    app.state.quota = RequestQuota(int(os.environ.get("CHAT_HOURLY_LIMIT", "20")),
                                  int(os.environ.get("CHAT_DAILY_LIMIT", "100")))
    app.state.chat_enabled = os.environ.get("CHAT_ENABLED", "true").lower() == "true"
    yield


app = FastAPI(title="Portfolio Assistant", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=2000)


@app.get("/")
def home():
    return FileResponse(FRONTEND / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat")
def chat(body: ChatRequest, request: Request):
    # Reject browser requests originating on another website. No CORS is enabled.
    origin = request.headers.get("origin")
    if origin and origin != (PUBLIC_ORIGIN or str(request.base_url).rstrip("/")):
        raise HTTPException(403, "Open the assistant on its own website.")
    if not request.app.state.chat_enabled:
        raise HTTPException(503, "The assistant is temporarily unavailable. Please try again later.")
    lock = request.app.state.generation_lock
    if not lock.acquire(blocking=False):
        raise HTTPException(429, "Another answer is being prepared. Please wait.")
    try:
        if not request.app.state.quota.allow():
            raise HTTPException(429, "The demo has reached its shared request limit. Please try again later.")
        result = request.app.state.assistant.ask(body.question)
    except LLMError:
        raise HTTPException(502, "Could not generate an answer. Please try again later.") from None
    except ValueError:
        raise HTTPException(400, "Could not prepare the question or portfolio context.") from None
    finally:
        lock.release()
    # Return only display data, not the complete corpus or provider metadata.
    return {
        "answer": result.answer,
        "status": result.status,
        "sources": [
            {"id": source.source_id, "title": source.title,
             "file": source.source, "text": source.text,
             "url": f"/api/sources/{source.source}"}
            for source in result.sources
        ],
    }


@app.get("/api/sources/{name}")
def original_source(name: str, request: Request):
    # Lookup only: never interpret a browser-supplied name as a filesystem path.
    source = request.app.state.originals.get(name)
    if source is None:
        raise HTTPException(404, "Unknown source.")
    return Response(source.original, media_type=source.media_type, headers={
        "Content-Disposition": f'inline; filename="{name}"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    })


if __name__ == "__main__":
    import uvicorn

    # Render uses its separate start command; this remains the local entry point.
    uvicorn.run(app, host="127.0.0.1", port=8000)
