"""Explicit full rebuilds: publish a new collection only after all writes succeed."""

import argparse
import hashlib
import json
import logging
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.chunking import chunk_document
from backend.config import EmbeddingConfig, IngestionConfig
from backend.embeddings import Embedder, SentenceTransformerEmbedder, passage_text
from backend.ingestion import load_documents
from backend.models import Document
from backend.vector_store import ChromaStore

logger = logging.getLogger(__name__)


def corpus_fingerprint(documents: list[Document]) -> str:
    content = [(doc.source, doc.title, doc.text) for doc in sorted(documents, key=lambda doc: doc.source)]
    return hashlib.sha256(json.dumps(content, ensure_ascii=False).encode("utf-8")).hexdigest()


def read_manifest(directory: Path) -> dict:
    try:
        manifest = json.loads((directory / "active.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("No index exists. Run python -m backend.indexing first.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Cannot read index manifest; rebuild the index.") from exc
    required = {"schema_version", "collection", "embedding", "chunk_count", "corpus_sha256"}
    if not isinstance(manifest, dict) or not required <= manifest.keys() or manifest["schema_version"] != 1:
        raise ValueError("Unsupported index manifest; rebuild the index.")
    return manifest


def rebuild_index(
    config: IngestionConfig, directory: Path, embedder: Embedder,
    *, store: ChromaStore | None = None,
) -> dict:
    documents = load_documents(config.data_dir)
    chunks = [chunk for doc in documents for chunk in chunk_document(doc, config)]
    # An empty corpus intentionally publishes an empty index, removing stale results.
    directory.mkdir(parents=True, exist_ok=True)
    store = store or ChromaStore(directory)
    name = "portfolio-" + uuid4().hex
    collection = store.create(name)
    temporary = directory / (name + ".json.tmp")
    manifest = {
        "schema_version": 1, "collection": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "embedding": asdict(embedder.config),
        "chunking": {"version": "v1", "size": config.chunk_size, "overlap": config.chunk_overlap},
        "passage_format": "title-section-text-v1", "distance": "cosine",
        "document_count": len(documents), "chunk_count": len(chunks),
        "corpus_sha256": corpus_fingerprint(documents),
        "sources": [doc.source for doc in documents],
    }
    try:
        for start in range(0, len(chunks), embedder.config.batch_size):
            batch = chunks[start:start + embedder.config.batch_size]
            vectors = embedder.embed_passages([passage_text(chunk) for chunk in batch])
            store.add(collection, batch, vectors)
        if collection.count() != len(chunks):
            raise RuntimeError("Index count does not match the source chunks")
        temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        os.replace(temporary, directory / "active.json")
    except Exception:
        # Only the unpublished collection is removed; the active index stays usable.
        try:
            store.delete(name)
            temporary.unlink(missing_ok=True)
        except Exception:
            logger.warning("Could not clean up unpublished index %s", name)
        raise
    logger.info("Published index: %d documents, %d chunks", len(documents), len(chunks))
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--db-dir", type=Path, default=Path("vector_db"))
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=150)
    parser.add_argument("--model", default=EmbeddingConfig().model_name)
    parser.add_argument("--revision", default="main", help="Use a model commit SHA for reproducibility")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--query-prefix", default="query: ")
    parser.add_argument("--passage-prefix", default="passage: ")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        config = IngestionConfig(args.data_dir, args.chunk_size, args.chunk_overlap)
        embedding = EmbeddingConfig(args.model, args.revision, args.query_prefix, args.passage_prefix, args.batch_size)
        manifest = rebuild_index(config, args.db_dir, SentenceTransformerEmbedder(embedding))
    except Exception as exc:
        parser.exit(1, f"Indexing failed: {exc}\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
