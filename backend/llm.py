"""Small provider interface and local Ollama HTTP adapter; no SDK required."""

import json
import socket
from dataclasses import dataclass, field
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.config import LLMConfig


class LLMError(RuntimeError):
    """A generation failed; never present this as a factual abstention."""


@dataclass(frozen=True)
class LLMResponse:
    content: str
    metrics: dict = field(default_factory=dict)


class LLMClient(Protocol):
    def generate(self, messages: list[dict[str, str]], schema: dict) -> LLMResponse: ...


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
