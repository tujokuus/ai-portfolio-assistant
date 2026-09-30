"""Query the active persisted index without rebuilding or generating an answer."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from backend.config import EmbeddingConfig
from backend.embeddings import Embedder, SentenceTransformerEmbedder
from backend.indexing import read_manifest
from backend.models import SearchResult
from backend.vector_store import ChromaStore


class Retriever:
    def __init__(self, directory: Path, *, embedder: Embedder | None = None, store=None) -> None:
        self.manifest = read_manifest(directory)
        config = EmbeddingConfig(**self.manifest["embedding"])
        if embedder is not None and embedder.config != config:
            raise ValueError("Query embedding configuration differs from the index; rebuild it")
        self.embedder = embedder or SentenceTransformerEmbedder(config)
        self.store = store or ChromaStore(directory)
        self.collection = self.store.get(self.manifest["collection"])
        if self.collection.count() != self.manifest["chunk_count"]:
            raise ValueError("Index is incomplete; rebuild it")

    def search(self, question: str, top_k: int = 5) -> list[SearchResult]:
        question = question.strip()
        if not question:
            raise ValueError("Question must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be positive")
        if not self.collection.count():
            return []
        return self.store.query(self.collection, self.embedder.embed_query(question), top_k)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--db-dir", type=Path, default=Path("vector_db"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        if not args.question.strip() or args.top_k < 1:
            raise ValueError("Provide a nonempty question and a positive --top-k")
        results = Retriever(args.db_dir).search(args.question, args.top_k)
    except Exception as exc:
        parser.exit(1, f"Search failed: {exc}\n")
    if args.as_json:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=True, indent=2))
    elif not results:
        print("The active index is empty. Add documents and rebuild it.")
    else:
        for rank, result in enumerate(results, 1):
            chunk = result.chunk
            print(f"\nResult {rank} | cosine distance: {result.distance:.6f} (lower is closer)")
            print(f"Source: {chunk.source}\nTitle: {chunk.title}\nSection: {chunk.section or '-'}")
            print(f"Chunk: {chunk.chunk_index} | ID: {chunk.chunk_id}\n{chunk.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
