"""Load UTF-8 portfolio files and preview their chunks without external services."""

import argparse
import json
import logging
from dataclasses import asdict
from pathlib import Path

from backend.chunking import chunk_document
from backend.config import IngestionConfig
from backend.markdown import headings
from backend.models import Document

logger = logging.getLogger(__name__)
SUPPORTED_SUFFIXES = {".md", ".txt"}


class DocumentLoadError(ValueError):
    """A supported document could not be read as UTF-8."""


def load_document(path: Path, *, data_dir: Path | None = None) -> Document:
    """Load one file; an explicit unsupported file is an error."""
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported document format: {path.suffix or '(none)'}")
    source = path.relative_to(data_dir).as_posix() if data_dir is not None else path.name
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise DocumentLoadError(f"Could not read {source} as UTF-8: {exc}") from exc
    title = path.stem
    if path.suffix.lower() == ".md":
        title = next((title for _, level, title in headings(text) if level == 1 and title), title)
    return Document(source=source, title=title, text=text)


def load_documents(data_dir: Path) -> list[Document]:
    """Recursively load supported files in stable order, skipping symlinks/other formats."""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise ValueError(f"Data directory does not exist or is not a directory: {data_dir}")
    documents: list[Document] = []
    logger.info("Document ingestion started")
    for path in sorted(data_dir.rglob("*")):
        relative = path.relative_to(data_dir)
        # Do not ingest files reached through symlinked directories either.
        linked_parent = any(
            (data_dir / parent).is_symlink()
            for parent in relative.parents if parent != Path(".")
        )
        if path.is_symlink() or linked_parent:
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            logger.debug("Skipping unsupported file: %s", relative.as_posix())
            continue
        documents.append(load_document(path, data_dir=data_dir))
    logger.info("Document ingestion completed: %d documents", len(documents))
    return documents


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--chunk-size", type=int, default=1000, help="Maximum characters (default: 1000)")
    parser.add_argument("--chunk-overlap", type=int, default=150, help="Overlap characters (default: 150)")
    args = parser.parse_args(argv)
    try:
        config = IngestionConfig(args.data_dir, args.chunk_size, args.chunk_overlap)
        documents = load_documents(config.data_dir)
        chunks = [chunk for document in documents for chunk in chunk_document(document, config)]
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps({
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "chunking": {"version": "v1", "unit": "characters", "size": config.chunk_size,
                     "overlap": config.chunk_overlap},
        "chunks": [asdict(chunk) for chunk in chunks],
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

