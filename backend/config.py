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

