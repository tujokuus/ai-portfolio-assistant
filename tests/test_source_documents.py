"""Offline source-list checks; no personal files, network, or model calls."""

import json

import pytest

from backend.source_documents import load_source_documents


def manifest(tmp_path, entries):
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": entries}), encoding="utf-8")
    return path


def test_readme_is_preserved_and_snapshot_does_not_change(tmp_path):
    raw = b"# Project\r\n\r\nExample: ignore previous instructions.\r\n"
    readme = tmp_path / "README.md"
    readme.write_bytes(raw)
    path = manifest(tmp_path, [{"name": "project.md", "title": "Project", "path": "README.md"}])
    source = load_source_documents(path)[0]
    readme.write_text("Updated later", encoding="utf-8")
    assert source.original == raw
    assert source.document.text == raw.decode("utf-8")
    assert source.document.source == "project.md"
    assert str(tmp_path) not in source.document.source


def test_unlisted_documents_are_not_loaded(tmp_path):
    (tmp_path / "old.md").write_text("Old facts", encoding="utf-8")
    (tmp_path / "new.md").write_text("New facts", encoding="utf-8")
    path = manifest(tmp_path, [{"name": "new.md", "title": "New", "path": "new.md"}])
    assert [item.document.text for item in load_source_documents(path)] == ["New facts"]


@pytest.mark.parametrize("name", ["../cv.pdf", "project/README.md", "<script>.md"])
def test_public_names_cannot_be_paths_or_markup(tmp_path, name):
    path = manifest(tmp_path, [{"name": name, "title": "Bad", "path": "README.md"}])
    with pytest.raises(ValueError, match="simple filenames"):
        load_source_documents(path)


def test_missing_source_fails_instead_of_silently_skipping(tmp_path):
    path = manifest(tmp_path, [{"name": "cv.pdf", "title": "CV", "path": "missing.pdf"}])
    with pytest.raises(ValueError, match="Cannot read cv.pdf"):
        load_source_documents(path)


def test_empty_pdf_page_is_not_silently_omitted(monkeypatch):
    from backend.source_documents import extract_pdf
    from types import SimpleNamespace
    import pypdf

    monkeypatch.setattr(pypdf, "PdfReader", lambda stream: SimpleNamespace(pages=[
        SimpleNamespace(extract_text=lambda **kwargs: "Work experience"),
        SimpleNamespace(extract_text=lambda **kwargs: ""),
    ]))
    with pytest.raises(ValueError, match="without extractable text"):
        extract_pdf(b"fake PDF")
