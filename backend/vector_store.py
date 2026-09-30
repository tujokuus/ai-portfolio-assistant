"""Chroma-specific persistence kept separate from ingestion and retrieval."""

from pathlib import Path

from backend.models import DocumentChunk, SearchResult


class ChromaStore:
    def __init__(self, directory: Path) -> None:
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError as exc:
            raise RuntimeError('Install retrieval dependencies: pip install -e ".[dev,retrieval]"') from exc
        self.client = chromadb.PersistentClient(
            path=str(directory), settings=Settings(anonymized_telemetry=False)
        )

    def create(self, name: str):
        return self.client.create_collection(
            name=name, embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
        )

    def get(self, name: str):
        return self.client.get_collection(name=name, embedding_function=None)

    def delete(self, name: str) -> None:
        self.client.delete_collection(name=name)

    @staticmethod
    def add(collection, chunks: list[DocumentChunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Each chunk must have exactly one embedding")
        if not chunks:
            return
        collection.add(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks], embeddings=vectors,
            metadatas=[{
                "source": chunk.source, "title": chunk.title,
                "section": chunk.section or "", "chunk_index": chunk.chunk_index,
            } for chunk in chunks],
        )

    @staticmethod
    def query(collection, vector: list[float], top_k: int) -> list[SearchResult]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        count = collection.count()
        if not count:
            return []
        result = collection.query(
            query_embeddings=[vector], n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
        return [SearchResult(
            chunk=DocumentChunk(
                chunk_id=identifier, source=metadata["source"], title=metadata["title"],
                section=metadata["section"] or None,
                chunk_index=int(metadata["chunk_index"]), text=text,
            ), distance=float(distance),
        ) for identifier, text, metadata, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0],
            result["distances"][0], strict=True,
        )]
