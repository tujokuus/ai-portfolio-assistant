"""Offline File Search contracts; no SDK, network or embedding model needed."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from backend.config import LLMConfig
from backend.file_search import FileSearchAssistant, decode_response, upload
from backend.llm import LLMError
from backend.models import Document

MANIFEST = {"files": {"file-known": {"source": "experience.md", "title": "Experience"}}}


def response(source="file-known", status="completed"):
    return {"status": status, "usage": {"input_tokens": 200, "output_tokens": 40}, "output": [
        {"type": "file_search_call", "status": "completed", "results": [
            {"file_id": "file-known", "text": "Tuomas used Databricks."}]},
        {"type": "message", "content": [{"type": "output_text", "text": json.dumps({
            "status": "answered", "statements": [{"text": "Tuomas used Databricks.",
            "source_ids": [source]}], "limitation": ""})}]}]}


def test_citations_resolve_only_to_retrieved_files():
    status, statements, limitation, sources, context, metrics = decode_response(response(), MANIFEST)
    assert sources[0].source == "experience.md"
    assert statements[0]["source_ids"] == ["S1"]
    assert context[0].text == "Tuomas used Databricks."
    assert metrics["file_search_calls"] == 1


@pytest.mark.parametrize("data", [response("file-invented"), response(status="incomplete")])
def test_invalid_answers_keep_usage(data):
    with pytest.raises(LLMError) as caught:
        decode_response(data, MANIFEST)
    assert caught.value.metrics["usage"]["input_tokens"] == 200


def test_out_of_scope_can_skip_search():
    data = {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps({"status": "insufficient", "statements": [],
         "limitation": "I can help with Tuomas's portfolio."})}]}]}
    result = decode_response(data, MANIFEST)
    assert result[0] == "insufficient" and result[3] == []
    assert result[5]["file_search_calls"] == 0


def test_stale_snapshot_fails_before_sdk_initialization(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema_version": 1, "status": "ready", "corpus_sha256": "stale"}))
    monkeypatch.setattr("backend.file_search.sdk_client", lambda *_: pytest.fail("No SDK expected"))
    with pytest.raises(ValueError, match="stale"):
        FileSearchAssistant(LLMConfig(provider="openai"), [Document("x.md", "X", "X")], path)


def test_failed_upload_preserves_ids(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    (data / "profile.md").write_text("# Profile\nEvidence", encoding="utf-8")
    client = SimpleNamespace(files=SimpleNamespace(create=lambda **_: SimpleNamespace(id="file-test")),
        vector_stores=SimpleNamespace(create=lambda **_: SimpleNamespace(id="vs-test"),
            files=SimpleNamespace(create=lambda **_: SimpleNamespace(status="failed"))))
    monkeypatch.setattr("backend.file_search.sdk_client", lambda *_: client)
    path = tmp_path / "manifest.json"
    with pytest.raises(LLMError, match="Indexing"):
        upload(data, path, LLMConfig())
    saved = json.loads(path.read_text())
    assert saved["vector_store_id"] == "vs-test"
    assert saved["files"]["file-test"]["source"] == "profile.md"
    assert saved["status"] == "uploading"
    with pytest.raises(ValueError, match="new manifest"):
        upload(data, path, LLMConfig())


def test_cloud_questions_have_current_evidence():
    root = Path(__file__).resolve().parents[1]
    cases = json.loads((root / "tests/evaluation_cloud_four.json").read_text(encoding="utf-8"))["cases"]
    assert len(cases) == 4 and cases[-1]["answer_mode"] == "out_of_scope"
    for case in cases:
        for evidence in case["evidence"]:
            assert evidence["quote"] in (root / "data" / evidence["source"]).read_text(encoding="utf-8")
