"""Local web interface: run with python -m backend.web from the repository."""

from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.config import LLMConfig
from backend.llm import LLMError, create_client
from backend.rag import PortfolioAssistant

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the corpus once. The API key stays in the server environment.
    config = LLMConfig(provider="openai", model="gpt-6-luna", timeout_seconds=60)
    app.state.assistant = PortfolioAssistant(
        create_client(config), config, mode="full", data_dir=ROOT / "data"
    )
    if not any(doc.text.strip() for doc in app.state.assistant.documents):
        raise RuntimeError("Add portfolio Markdown documents to data/ before starting.")
    app.state.generation_lock = Lock()
    yield


app = FastAPI(title="Portfolio Assistant", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
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
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Open the assistant in its local browser page.")
    lock = request.app.state.generation_lock
    if not lock.acquire(blocking=False):
        raise HTTPException(429, "Another answer is being prepared. Please wait.")
    try:
        result = request.app.state.assistant.ask(body.question)
    except LLMError as exc:
        # LLMError messages are sanitized by the existing provider adapter.
        raise HTTPException(502, str(exc)) from None
    except ValueError:
        raise HTTPException(400, "Could not prepare the question or portfolio context.") from None
    finally:
        lock.release()
    # Return only display data, not the complete corpus or provider metadata.
    return {
        "answer": result.answer,
        "status": result.status,
        "sources": [
            {"id": source.source_id, "title": source.title, "file": source.source}
            for source in result.sources
        ],
    }


if __name__ == "__main__":
    import uvicorn

    # Local use only. Public deployment requires separate abuse controls.
    uvicorn.run(app, host="127.0.0.1", port=8000)
