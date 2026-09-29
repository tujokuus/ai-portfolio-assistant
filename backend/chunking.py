"""Deterministic, heading-aware character windows with bounded overlap."""

import hashlib
import json
from collections.abc import Iterator
from pathlib import PurePosixPath

from backend.config import IngestionConfig
from backend.markdown import headings
from backend.models import Document, DocumentChunk


def _sections(document: Document) -> Iterator[tuple[str | None, str]]:
    if PurePosixPath(document.source).suffix.lower() != ".md":
        yield None, document.text
        return

    start = 0
    section = None
    hierarchy: list[tuple[int, str]] = []
    for offset, level, title in headings(document.text):
        if offset > start:
            yield section, document.text[start:offset]
        hierarchy = [(depth, name) for depth, name in hierarchy if depth < level]
        hierarchy.append((level, title))
        section = " > ".join(name for _, name in hierarchy if name) or None
        start = offset
    yield section, document.text[start:]


def _windows(text: str, size: int, overlap: int) -> Iterator[str]:
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # Prefer a whitespace boundary in the latter half of the window.
            # Keep end > start + overlap so even large overlaps make progress.
            lower = start + max(size // 2, overlap + 1)
            for boundary in range(end, lower - 1, -1):
                if text[boundary - 1].isspace():
                    end = boundary
                    break
        chunk = text[start:end].strip()
        if chunk:
            yield chunk
        if end == len(text):
            break
        start = end - overlap


def chunk_document(
    document: Document, config: IngestionConfig | None = None
) -> list[DocumentChunk]:
    """Keep sections separate; identical inputs and settings produce identical IDs."""
    config = config or IngestionConfig()
    chunks: list[DocumentChunk] = []
    for section, text in _sections(document):
        for window in _windows(text, config.chunk_size, config.chunk_overlap):
            index = len(chunks)
            identity = json.dumps(
                ["v1", document.source, document.title, section, index, window,
                 config.chunk_size, config.chunk_overlap],
                ensure_ascii=False,
            )
            chunks.append(DocumentChunk(
                chunk_id=hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                source=document.source,
                title=document.title,
                section=section,
                chunk_index=index,
                text=window,
            ))
    return chunks

