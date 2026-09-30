"""Local embeddings, with explicit prefixes and no silent token truncation."""

from typing import Protocol

from backend.config import EmbeddingConfig
from backend.models import DocumentChunk


class Embedder(Protocol):
    config: EmbeddingConfig

    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def passage_text(chunk: DocumentChunk) -> str:
    """Keep title and heading context even on continuation chunks."""
    return f"{chunk.title}\n{chunk.section or ''}\n{chunk.text}"


class SentenceTransformerEmbedder:
    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        self.config = config or EmbeddingConfig()
        self._model = None

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError('Install retrieval dependencies: pip install -e ".[dev,retrieval]"') from exc
            self._model = SentenceTransformer(
                self.config.model_name, revision=self.config.revision, device="cpu",
                trust_remote_code=False,
            )
        tokens = self._model.tokenizer(texts, truncation=False, add_special_tokens=True)
        limit = self._model.max_seq_length
        if any(len(ids) > limit for ids in tokens["input_ids"]):
            raise ValueError(
                f"Embedding input exceeds {limit} tokens including title/prefix. "
                "Rebuild with a smaller --chunk-size, shorten headings, or shorten the question."
            )
        return self._model.encode(
            texts, batch_size=self.config.batch_size,
            normalize_embeddings=True, show_progress_bar=False,
        ).tolist()

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return self._encode([self.config.passage_prefix + text for text in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._encode([self.config.query_prefix + text])[0]
