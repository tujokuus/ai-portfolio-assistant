"""Explicit configuration shared by the CLI and Python callers."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IngestionConfig:
    """Chunk limits are Unicode characters, not embedding or LLM tokens."""

    data_dir: Path = Path("data")
    chunk_size: int = 1000
    chunk_overlap: int = 150

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("chunk_overlap must be non-negative and less than chunk_size")


@dataclass(frozen=True)
class EmbeddingConfig:
    model_name: str = "intfloat/multilingual-e5-small"
    revision: str = "main"
    query_prefix: str = "query: "
    passage_prefix: str = "passage: "
    batch_size: int = 16

    def __post_init__(self) -> None:
        if not self.model_name.strip() or not self.revision.strip():
            raise ValueError("Embedding model and revision must not be empty")
        if self.batch_size < 1:
            raise ValueError("batch_size must be positive")


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "ollama"
    model: str = "qwen3:4b-instruct"
    base_url: str = "http://localhost:11434"
    timeout_seconds: float = 180
    num_ctx: int = 32768
    max_output_tokens: int = 1024
    max_question_chars: int = 2000
    reasoning_effort: str = "none"

    def __post_init__(self) -> None:
        from math import isfinite
        from urllib.parse import urlparse

        if self.provider not in {"ollama", "openai"}:
            raise ValueError("Provider must be ollama or openai")
        if self.reasoning_effort not in {"none", "low", "medium", "high"}:
            raise ValueError("Unsupported reasoning effort")
        url = urlparse(self.base_url)
        if url.scheme not in {"http", "https"} or not url.hostname:
            raise ValueError("Ollama URL must be an HTTP(S) server URL")
        if not self.model.strip():
            raise ValueError("Model must not be empty")
        if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("Timeout must be positive and finite")
        if self.max_output_tokens < 1 or self.max_question_chars < 1:
            raise ValueError("Output and question limits must be positive")
        if self.num_ctx <= self.max_output_tokens + 1024:
            raise ValueError("Context window must leave room for input and template overhead")

