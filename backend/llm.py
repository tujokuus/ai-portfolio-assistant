"""Ollama and OpenAI HTTP adapters behind a shared interface; no SDK required."""

import json
import os
import socket
from dataclasses import dataclass, field
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.config import LLMConfig


class LLMError(RuntimeError):
    """A generation failed; never present this as a factual abstention."""

    def __init__(self, message: str, *, metrics: dict | None = None):
        super().__init__(message)
        self.metrics = metrics or {}


@dataclass(frozen=True)
class LLMResponse:
    content: str
    metrics: dict = field(default_factory=dict)


class LLMClient(Protocol):
    def generate(self, messages: list[dict[str, str]], schema: dict) -> LLMResponse: ...


def create_client(config: LLMConfig) -> LLMClient:
    return OpenAIClient(config) if config.provider == "openai" else OllamaClient(config)


class OpenAIClient:
    """Responses API adapter. One request, no automatic paid retries or tools."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not self._api_key:
            raise LLMError("Set OPENAI_API_KEY in the environment before selecting --provider openai.")

    def generate(self, messages: list[dict[str, str]], schema: dict) -> LLMResponse:
        payload = {
            "model": self.config.model, "input": messages, "store": False,
            "service_tier": "default", "truncation": "disabled",
            "reasoning": {"effort": self.config.reasoning_effort},
            "max_output_tokens": self.config.max_output_tokens,
            "text": {"format": {"type": "json_schema", "name": "portfolio_answer",
                                "strict": True, "schema": schema}},
        }
        request = Request("https://api.openai.com/v1/responses",
                          data=json.dumps(payload).encode("utf-8"), method="POST",
                          headers={"Content-Type": "application/json",
                                   "Authorization": "Bearer " + self._api_key})
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise LLMError("OpenAI response is unexpectedly large")
            data = json.loads(raw)
        except HTTPError as exc:
            hints = {401: "Check OPENAI_API_KEY.", 403: "Check project permissions.",
                     404: "Check model availability for this API project.",
                     429: "Check API quota, billing and rate limits.",
                     400: "Check model support for reasoning effort and structured output."}
            # Do not expose provider error bodies, request headers or credentials.
            raise LLMError(f"OpenAI returned HTTP {exc.code}. " +
                           hints.get(exc.code, "Check the API service status.")) from None
        except (TimeoutError, socket.timeout, URLError, OSError) as exc:
            raise LLMError("OpenAI connection failed or timed out. No automatic retry was made; "
                           "the request may already have been billed.") from None
        except ValueError:
            raise LLMError("OpenAI returned invalid JSON") from None
        if not isinstance(data, dict):
            raise LLMError("OpenAI returned an unexpected response")
        metrics = {"provider": "openai", "model": data.get("model", self.config.model),
                   "response_id": data.get("id"), "usage": data.get("usage"),
                   "service_tier": data.get("service_tier"), "model_called": True}
        if data.get("status") != "completed":
            raise LLMError("OpenAI generation did not complete. Check output limits and API status.",
                           metrics=metrics)
        texts = []
        output = data.get("output")
        if not isinstance(output, list):
            raise LLMError("OpenAI returned invalid output", metrics=metrics)
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                raise LLMError("OpenAI returned invalid message content", metrics=metrics)
            for part in content:
                if not isinstance(part, dict):
                    raise LLMError("OpenAI returned invalid content item", metrics=metrics)
                if part.get("type") == "refusal":
                    raise LLMError("OpenAI refused this request.", metrics=metrics)
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    texts.append(part["text"])
        if not texts:
            raise LLMError("OpenAI returned no answer text", metrics=metrics)
        return LLMResponse("".join(texts), metrics)


class OllamaClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def generate(self, messages: list[dict[str, str]], schema: dict) -> LLMResponse:
        payload = {
            "model": self.config.model, "messages": messages, "format": schema,
            "stream": False, "keep_alive": "5m",
            "options": {
                "temperature": 0, "seed": 42,
                "num_ctx": self.config.num_ctx,
                "num_predict": self.config.max_output_tokens,
            },
        }
        request = Request(
            self.config.base_url.rstrip("/") + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise LLMError("Ollama response is unexpectedly large")
            data = json.loads(raw)
        except HTTPError as exc:
            if exc.code == 404:
                raise LLMError(
                    f"Ollama model or endpoint not found. Check the URL and run: ollama pull {self.config.model}"
                ) from exc
            raise LLMError(
                f"Ollama returned HTTP {exc.code}. Check its logs, model availability, and memory."
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMError("Ollama request timed out. Try --timeout 300 or a smaller model.") from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise LLMError("Ollama request timed out. Try --timeout 300.") from exc
            raise LLMError("Cannot connect to Ollama. Start Ollama and check --ollama-url.") from exc
        except (OSError, ValueError) as exc:
            raise LLMError("Could not read a valid JSON response from Ollama.") from exc
        if not isinstance(data, dict) or data.get("error"):
            raise LLMError("Ollama returned an error response. Check the server logs.")
        if data.get("done") is not True or data.get("done_reason") == "length":
            raise LLMError("Generation was incomplete. Increase --max-output-tokens or use a shorter answer.")
        message = data.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise LLMError("Ollama response has no assistant content")
        count = data.get("prompt_eval_count")
        if isinstance(count, int) and count + self.config.max_output_tokens >= self.config.num_ctx:
            raise LLMError("Prompt approached the context limit; increase --num-ctx and retry.")
        fields = ("model", "total_duration", "load_duration", "prompt_eval_count",
                  "prompt_eval_duration", "eval_count", "eval_duration", "done_reason")
        return LLMResponse(message["content"], {key: data[key] for key in fields if key in data})
