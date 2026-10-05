"""Read an explicit local source list without AI summaries or network requests."""

import argparse
import json
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from backend.models import Document


@dataclass(frozen=True)
class SourceDocument:
    document: Document
    original: bytes
    media_type: str


def extract_pdf(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ValueError('PDF support requires: pip install -e ".[web]"') from None
    try:
        reader = PdfReader(BytesIO(raw))
        pages = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
    except Exception:
        raise ValueError("Cannot read PDF. Use a readable, unencrypted text PDF.") from None
    if not pages or any(not page.strip() for page in pages):
        raise ValueError("PDF contains a page without extractable text; check whether OCR is needed.")
    # Only remove trailing spaces and excessive blank lines, never summarize.
    text = "\n\n".join(pages)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def load_source_documents(manifest: Path) -> list[SourceDocument]:
    """Snapshot only explicitly listed files. Paths resolve relative to the manifest."""
    manifest = Path(manifest).resolve()
    data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    entries = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError("Source list must contain a non-empty sources array.")
    loaded = []
    names = set()
    for entry in entries:
        if not isinstance(entry, dict) or any(
            not isinstance(entry.get(key), str) or not entry[key].strip()
            for key in ("name", "title", "path")
        ):
            raise ValueError("Each source needs a name, title, and local path.")
        name = entry["name"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) or name in names:
            raise ValueError("Source names must be unique, simple filenames.")
        path = (manifest.parent / entry["path"]).resolve()
        suffix = path.suffix.lower()
        if suffix not in {".pdf", ".md", ".txt"} or Path(name).suffix.lower() != suffix:
            raise ValueError(f"Unsupported or mismatched file type for {name}.")
        try:
            raw = path.read_bytes()
            text = extract_pdf(raw) if suffix == ".pdf" else raw.decode("utf-8-sig")
        except (OSError, UnicodeError):
            raise ValueError(f"Cannot read {name}; check its local path and encoding.") from None
        if not text.strip():
            raise ValueError(f"Source is empty: {name}")
        names.add(name)
        loaded.append(SourceDocument(
            Document(source=name, title=entry["title"], text=text), raw,
            "application/pdf" if suffix == ".pdf" else "text/plain",
        ))
    return loaded


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview original-source extraction without an API call.")
    parser.add_argument("--sources", type=Path, default=Path("sources.local.json"))
    args = parser.parse_args()
    for source in load_source_documents(args.sources):
        print(f"\n--- {source.document.source}: {source.document.title} ---\n")
        print(source.document.text)


if __name__ == "__main__":
    main()
