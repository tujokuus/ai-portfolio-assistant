"""Synthetic offline evaluation checks. These tests never use a real provider."""

import json

import pytest

from backend import compare
from backend.llm import LLMResponse


def setup_case(tmp_path):
    (tmp_path / "new.md").write_text("New supported fact.", encoding="utf-8")
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({"sources": [
        {"name": "new.md", "title": "New", "path": "new.md"}
    ]}), encoding="utf-8")
    dataset = tmp_path / "cases.json"
    case = {"id": "one", "question": "What is supported?", "answer_mode": "answer",
            "required_facts": ["REVIEW_ONLY_MARKER"], "forbidden_claims": [],
            "expected_sources": ["new.md"],
            "evidence": [{"source": "new.md", "quote": "New supported fact."}]}
    dataset.write_text(json.dumps({"schema_version": 1, "cases": [case, {**case, "id": "two"}]}), encoding="utf-8")
    output = tmp_path / "report.json"
    args = ["--provider", "openai", "--sources", str(sources), "--dataset", str(dataset),
            "--suite", "all", "--output", str(output)]
    return args, dataset, output


def forbid_client(config):
    pytest.fail("Validation must not initialize a provider")


def test_validate_only_needs_no_key_and_writes_no_report(tmp_path, monkeypatch):
    args, _, output = setup_case(tmp_path)
    monkeypatch.setattr(compare, "create_client", forbid_client)
    assert compare.main(args + ["--validate-only"]) == 0
    assert not output.exists()
    output.write_text("existing report")
    assert compare.main(args + ["--validate-only"]) == 0
    assert output.read_text() == "existing report"


def test_stale_reference_fails_before_provider(tmp_path, monkeypatch):
    args, dataset, _ = setup_case(tmp_path)
    dataset.write_text(dataset.read_text().replace("New supported fact.", "Missing fact."))
    monkeypatch.setattr(compare, "create_client", forbid_client)
    with pytest.raises(SystemExit):
        compare.main(args)


def test_context_overflow_fails_before_provider(tmp_path, monkeypatch):
    args, _, _ = setup_case(tmp_path)
    (tmp_path / "new.md").write_text("New supported fact." + "x" * 40000)
    monkeypatch.setattr(compare, "create_client", forbid_client)
    with pytest.raises(SystemExit):
        compare.main(args + ["--num-ctx", "32768"])


def test_two_corpora_alternate_and_keep_missing_evidence_separate(tmp_path, monkeypatch):
    args, _, output = setup_case(tmp_path)
    old = tmp_path / "old"
    old.mkdir()
    (old / "old.md").write_text("Older fact.")
    calls = []

    class Client:
        def generate(self, messages, schema):
            serialized = json.dumps(messages)
            assert "REVIEW_ONLY_MARKER" not in serialized
            calls.append(serialized)
            return LLMResponse(json.dumps({"status": "insufficient", "statements": [],
                                           "limitation": "No supported answer."}),
                               {"model": "fake", "usage": {"input_tokens": 10, "output_tokens": 4}})

    monkeypatch.setattr(compare, "create_client", lambda config: Client())
    assert compare.main(args + ["--compare-data-dir", str(old)]) == 0
    report = json.loads(output.read_text())
    assert len(calls) == 4
    assert report["requested_generations"] == 4
    assert report["cases"][0]["order"] == ["primary", "comparison"]
    assert report["cases"][1]["order"] == ["comparison", "primary"]
    assert report["corpora"]["primary"]["corpus_sha256"] != report["corpora"]["comparison"]["corpus_sha256"]
    assert report["reference_coverage"]["comparison"]["one"]["missing_sources"] == ["new.md"]
    assert report["summary"]["comparison"]["errors"] == 0
    assert report["summary"]["primary"]["input_tokens"] == 20
    assert report["cases"][0]["manual_review"]["primary"]["facts_supported"] is None
    with pytest.raises(SystemExit):
        compare.main(args)  # Preserve existing reports, without a second model call.
    assert len(calls) == 4


def test_pdf_whitespace_matching_is_explicit():
    from backend.models import Document
    docs = [Document("cv.pdf", "CV", "LIBS   spectroscopy\n data")]
    cases = [{"id": "pdf", "evidence": [{"source": "cv.pdf", "quote": "LIBS spectroscopy data"}]}]
    assert compare.reference_coverage(cases, docs)["pdf"]["unmatched_evidence"]
    assert not compare.reference_coverage(cases, docs, normalize=True)["pdf"]["unmatched_evidence"]
