"""Verify boundaries, evidence metadata, reproducibility, and edge cases."""

from dataclasses import replace

import pytest

from backend.chunking import chunk_document
from backend.config import IngestionConfig
from backend.models import Document


@pytest.mark.parametrize("size,overlap", [(0, 0), (-1, 0), (10, -1), (10, 10), (10, 11)])
def test_invalid_configuration(size, overlap):
    with pytest.raises(ValueError):
        IngestionConfig(chunk_size=size, chunk_overlap=overlap)


@pytest.mark.parametrize("text", ["", " \n\t  "])
def test_empty_documents_produce_no_chunks(text):
    assert chunk_document(Document("empty.md", "Empty", text)) == []


def test_short_text_kept_in_one_chunk():
    chunks = chunk_document(Document("sample.txt", "Sample", "A short example."))
    assert len(chunks) == 1
    assert chunks[0].text == "A short example."
    assert chunks[0].section is None


@pytest.mark.parametrize("overlap", [0, 3, 9])
def test_windows_cover_content_and_enforce_size(overlap):
    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    chunks = chunk_document(Document("sample.txt", "Sample", text), IngestionConfig(chunk_size=10, chunk_overlap=overlap))
    reconstructed = chunks[0].text + "".join(chunk.text[overlap:] for chunk in chunks[1:])
    assert reconstructed == text
    assert all(0 < len(chunk.text) <= 10 for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_word_boundaries_do_not_lose_words():
    words = [f"word{i}" for i in range(100)]
    chunks = chunk_document(Document("sample.txt", "Sample", " ".join(words)), IngestionConfig(chunk_size=50, chunk_overlap=10))
    seen = {word for chunk in chunks for word in chunk.text.split()}
    assert set(words) <= seen
    assert all(len(chunk.text) <= 50 for chunk in chunks)


def test_heading_sections_preserve_metadata_without_crossing_boundaries():
    document = Document("projects/sample.md", "Sample", "Preamble\n# Sample\nIntro\n## Tools\nPython\n### Testing\npytest\n## Results\nSynthetic only")
    chunks = chunk_document(document)
    assert [chunk.section for chunk in chunks] == [None, "Sample", "Sample > Tools", "Sample > Tools > Testing", "Sample > Results"]
    assert all(chunk.source == "projects/sample.md" and chunk.title == "Sample" for chunk in chunks)
    assert "Results" not in chunks[3].text
    assert "pytest" not in chunks[4].text


def test_continuation_chunks_retain_section():
    document = Document("sample.md", "Sample", "# Sample\n## Details\n" + "Evidence " * 30)
    chunks = chunk_document(document, IngestionConfig(chunk_size=40, chunk_overlap=5))
    assert len(chunks) > 3
    assert all(chunk.section == "Sample > Details" for chunk in chunks[1:])


@pytest.mark.parametrize("fence", ["```", "~~~~"])
def test_headings_inside_fenced_code_are_not_sections(fence):
    document = Document("sample.md", "Sample", f"# Sample\n{fence}python\n# Code comment\n{fence}\n## Real section\nBody")
    assert [chunk.section for chunk in chunk_document(document)] == ["Sample", "Sample > Real section"]


def test_text_file_hashes_are_not_headings():
    chunks = chunk_document(Document("sample.txt", "Sample", "# Literal\n## Also literal\nText"))
    assert len(chunks) == 1
    assert chunks[0].section is None


def test_ids_are_reproducible_and_distinguish_sources_content_and_settings():
    document = Document("sample.txt", "Sample", "Example evidence")
    original = chunk_document(document)
    assert original == chunk_document(document)
    assert original[0].chunk_id != chunk_document(replace(document, source="nested/sample.txt"))[0].chunk_id
    assert original[0].chunk_id != chunk_document(replace(document, text="Changed evidence"))[0].chunk_id
    assert original[0].chunk_id != chunk_document(document, IngestionConfig(chunk_size=900))[0].chunk_id


def test_duplicate_sections_still_have_unique_ids():
    chunks = chunk_document(Document("sample.md", "Sample", "## Same\nText\n## Same\nText\n"))
    assert len({chunk.chunk_id for chunk in chunks}) == 2


def test_smallest_window_terminates():
    chunks = chunk_document(Document("sample.txt", "Sample", "a b"), IngestionConfig(chunk_size=1, chunk_overlap=0))
    assert [chunk.text for chunk in chunks] == ["a", "b"]

