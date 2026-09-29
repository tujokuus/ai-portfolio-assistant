"""Loader and CLI contracts, using only temporary synthetic documents."""

import json
from pathlib import Path

import pytest

from backend.ingestion import DocumentLoadError, load_document, load_documents, main


def test_markdown_loading_with_bom_and_title(tmp_path):
    path = tmp_path / "project.md"
    path.write_text("\ufeff# Sample project\n\nUnicode: ää, 日本語.\n", encoding="utf-8")
    document = load_document(path)
    assert document.source == "project.md"
    assert document.title == "Sample project"
    assert document.text == "# Sample project\n\nUnicode: ää, 日本語.\n"


def test_text_loading_preserves_content_and_uses_stem(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("# Literal text\nA sample.", encoding="utf-8")
    document = load_document(path)
    assert document.title == "sample"
    assert document.text == "# Literal text\nA sample."


def test_markdown_without_h1_uses_filename(tmp_path):
    path = tmp_path / "sample.md"
    path.write_text("## Details\nBody", encoding="utf-8")
    assert load_document(path).title == "sample"


def test_title_ignores_fenced_headings_and_removes_closing_hashes(tmp_path):
    path = tmp_path / "sample.md"
    path.write_text("```\n# Not a title\n```\n# Real title ###\nBody", encoding="utf-8")
    assert load_document(path).title == "Real title"


def test_symlink_file_is_skipped(tmp_path, monkeypatch):
    path = tmp_path / "link.txt"
    path.write_text("External sample", encoding="utf-8")
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: self == path or original(self))
    assert load_documents(tmp_path) == []


def test_scan_is_recursive_sorted_and_skips_unsupported_files(tmp_path):
    (tmp_path / "nested").mkdir()
    for name in ("z.txt", "a.MD", "nested/a.md", "ignored.pdf"):
        (tmp_path / name).write_text("Sample", encoding="utf-8")
    assert [doc.source for doc in load_documents(tmp_path)] == ["a.MD", "nested/a.md", "z.txt"]


def test_explicit_unsupported_file_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unsupported document format"):
        load_document(tmp_path / "sample.pdf")


def test_empty_directory_and_document(tmp_path):
    assert load_documents(tmp_path) == []
    (tmp_path / "empty.md").write_text("", encoding="utf-8")
    assert load_documents(tmp_path)[0].text == ""


def test_missing_directory_is_reported(tmp_path):
    with pytest.raises(ValueError, match="Data directory"):
        load_documents(tmp_path / "missing")


def test_invalid_utf8_is_reported(tmp_path):
    (tmp_path / "invalid.txt").write_bytes(b"\xff\xfe\xff")
    with pytest.raises(DocumentLoadError, match="invalid.txt.*UTF-8"):
        load_documents(tmp_path)


def test_unreadable_file_is_reported(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError("Access denied")
    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(DocumentLoadError, match="Could not read sample.txt"):
        load_document(tmp_path / "sample.txt")


def test_cli_outputs_json(tmp_path, capsys):
    (tmp_path / "sample.md").write_text("# Example\n\nBody text", encoding="utf-8")
    assert main(["--data-dir", str(tmp_path), "--chunk-size", "40", "--chunk-overlap", "5"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["document_count"] == 1
    assert payload["chunk_count"] == 1
    assert payload["chunks"][0]["source"] == "sample.md"
    assert payload["chunks"][0]["section"] == "Example"
    assert payload["chunking"]["size"] == 40


def test_cli_missing_directory_has_no_traceback(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--data-dir", str(tmp_path / "missing")])
    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "Data directory" in error
    assert "Traceback" not in error


def test_cli_rejects_invalid_configuration(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--chunk-size", "0"])
    assert exc.value.code == 2
    assert "chunk_size" in capsys.readouterr().err

