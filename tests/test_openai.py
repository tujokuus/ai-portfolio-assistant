"""Offline API contract checks; never call OpenAI or load embedding models."""

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from backend.ask import add_options, llm_config
from backend.compare import compare_case, summarize_results
from backend.compare import SMOKE_CASE_IDS
from backend.config import LLMConfig
from backend.llm import LLMError, LLMResponse, OpenAIClient, create_client
from backend.models import Document
from backend.rag import ANSWER_SCHEMA, PortfolioAssistant


def api_response(**changes):
    return {"status": "completed", "id": "resp_test", "model": "gpt-6-luna",
            "usage": {"input_tokens": 120, "output_tokens": 30,
                      "output_tokens_details": {"reasoning_tokens": 5}},
            "output": [{"type": "reasoning"}, {"type": "message", "content": [
                {"type": "output_text", "text": '{"status":"insufficient","statements":[],"limitation":"No evidence."}'}]}],
            **changes}


def install_response(monkeypatch, data):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    seen = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, size):
            return json.dumps(data).encode()

    def fake_open(request, timeout):
        seen.append((request, timeout))
        return Response()

    monkeypatch.setattr("backend.llm.urlopen", fake_open)
    return seen


def test_responses_request_and_usage(monkeypatch):
    seen = install_response(monkeypatch, api_response())
    client = OpenAIClient(LLMConfig(provider="openai", model="gpt-6-luna"))
    response = client.generate([{"role": "user", "content": "Question"}], ANSWER_SCHEMA)
    request, timeout = seen[0]
    body = json.loads(request.data)
    assert request.full_url == "https://api.openai.com/v1/responses"
    assert body["store"] is False and body["truncation"] == "disabled"
    assert body["text"]["format"]["schema"] == ANSWER_SCHEMA
    assert body["text"]["format"]["strict"] is True
    assert body["reasoning"] == {"effort": "none"}
    assert "tools" not in body and "temperature" not in body and "seed" not in body
    assert response.metrics["usage"]["input_tokens"] == 120
    assert "test-secret" not in json.dumps(response.metrics)
    assert json.loads(response.content)["status"] == "insufficient"


@pytest.mark.parametrize("data", [
    api_response(status="incomplete"),
    api_response(output=[{"type": "message", "content": [{"type": "refusal"}]}]),
    api_response(output=[]),
])
def test_failed_generation_keeps_usage(monkeypatch, data):
    seen = install_response(monkeypatch, data)
    with pytest.raises(LLMError) as caught:
        OpenAIClient(LLMConfig()).generate([], ANSWER_SCHEMA)
    assert caught.value.metrics["usage"]["output_tokens"] == 30
    assert len(seen) == 1


def test_auth_failure_does_not_retry_or_expose_error_body(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise HTTPError("https://api.openai.com/v1/responses", 401, "test-secret", {}, None)

    monkeypatch.setattr("backend.llm.urlopen", fail)
    with pytest.raises(LLMError, match="401") as caught:
        OpenAIClient(LLMConfig()).generate([], ANSWER_SCHEMA)
    assert "test-secret" not in str(caught.value)
    assert len(calls) == 1


def test_provider_defaults_and_missing_key(monkeypatch):
    parser = argparse.ArgumentParser()
    add_options(parser)
    assert llm_config(parser.parse_args([])).provider == "ollama"
    config = llm_config(parser.parse_args(["--provider", "openai"]))
    assert config.model == "gpt-6-luna"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        create_client(config)


def test_validation_error_usage_survives_comparison():
    class BadClient:
        def generate(self, messages, schema):
            return LLMResponse("not json", {"usage": api_response()["usage"]})

    assistant = PortfolioAssistant(BadClient(), LLMConfig(),
                                   documents=[Document("test.md", "Test", "Evidence")])
    row = compare_case({"id": "test", "question": "Question?"}, {"full": assistant}, ["full"])
    summary = summarize_results([row], ["full"])["full"]
    assert not row["results"]["full"]["ok"]
    assert summary["input_tokens"] == 120
    assert summary["output_tokens"] == 30
    assert summary["reasoning_tokens"] == 5  # Already included in the 30 output tokens.
    assert summary["responses_with_usage"] == 1


def test_english_suite_references_match_documents():
    root = Path(__file__).resolve().parents[1]
    dataset = json.loads((root / "tests/evaluation_smoke_en.json").read_text(encoding="utf-8"))
    assert dataset["schema_version"] == 1
    assert tuple(case["id"] for case in dataset["cases"]) == SMOKE_CASE_IDS
    for case in dataset["cases"]:
        assert case["question"] and case["required_facts"] and case["forbidden_claims"]
        for evidence in case["evidence"]:
            text = (root / "data" / evidence["source"]).read_text(encoding="utf-8")
            assert evidence["quote"] in text
