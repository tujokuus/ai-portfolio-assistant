"""Immutable document and chunk records independent of future storage tools."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    source: str  # POSIX path relative to the supplied data directory.
    title: str
    text: str


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    source: str
    title: str
    section: str | None
    chunk_index: int  # Zero-based within the document.
    text: str


@dataclass(frozen=True)
class SearchResult:
    chunk: DocumentChunk
    distance: float  # Chroma cosine distance: lower is closer, not confidence.

