"""Upload a portfolio snapshot and answer with OpenAI's hosted File Search tool."""

import argparse
import json
import os
from pathlib import Path
from time import monotonic, perf_counter, sleep

from backend.config import LLMConfig
from backend.indexing import corpus_fingerprint
from backend.ingestion import load_documents
from backend.llm import LLMError
from backend.rag import ANSWER_SCHEMA, SYSTEM_PROMPT, Answer, Evidence, parse_answer


def sdk_client(config):
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise LLMError("Set OPENAI_API_KEY before using File Search.")
    try:
        from openai import OpenAI
    except ImportError:
        raise LLMError('Install the optional SDK: python -m pip install -e ".[cloud]"') from None
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url="https://api.openai.com/v1",
                  timeout=config.timeout_seconds, max_retries=0)


def remote(call, **kwargs):
    """Avoid recording SDK exception bodies or credentials in reports."""
    try:
        return call(**kwargs)
    except Exception as exc:
        code = getattr(exc, "status_code", None)
        raise LLMError(f"OpenAI File Search request failed (HTTP {code or 'unavailable'}). "
                       "Check credentials, billing, model support and connectivity. "
                       "No retry was made; inspect remote resources before repeating uploads.") from None


def write_manifest(path, manifest):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def upload(data_dir, manifest_path, config):
    path = manifest_path.resolve()
    if path.exists() or path.is_relative_to(data_dir.resolve()):
        raise ValueError("Choose a new manifest filename outside the portfolio data directory.")
    documents = load_documents(data_dir)
    if not documents or any(not doc.text.strip() for doc in documents):
        raise ValueError("Upload requires a nonempty corpus with no empty documents.")
    client = sdk_client(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "status": "uploading", "files": {},
                "corpus_sha256": corpus_fingerprint(documents), "vector_store_id": None}
    write_manifest(path, manifest)
    store = remote(client.vector_stores.create, name="Portfolio comparison",
                   expires_after={"anchor": "last_active_at", "days": 7})
    manifest["vector_store_id"] = store.id
    write_manifest(path, manifest)
    print(f"Created {store.id}; manifest: {path}", flush=True)
    for index, doc in enumerate(documents, 1):
        # Upload exactly the normalized snapshot used by full mode, not arbitrary files.
        file = remote(client.files.create, purpose="assistants",
                      file=(f"{index:03d}-{Path(doc.source).name}", doc.text.encode("utf-8")))
        manifest["files"][file.id] = {"source": doc.source, "title": doc.title}
        write_manifest(path, manifest)  # Preserve IDs even if indexing fails.
        attached = remote(client.vector_stores.files.create, vector_store_id=store.id, file_id=file.id)
        deadline = monotonic() + config.timeout_seconds
        while attached.status == "in_progress" and monotonic() < deadline:
            sleep(1)
            attached = remote(client.vector_stores.files.retrieve, vector_store_id=store.id, file_id=file.id)
        if attached.status != "completed":
            raise LLMError(f"Indexing did not complete for {doc.source}. IDs are saved in {path}.")
        print(f"Indexed {index}/{len(documents)}: {doc.source}", flush=True)
    manifest["status"] = "ready"
    write_manifest(path, manifest)
    return manifest


def decode_response(data, manifest):
    calls = [item for item in data.get("output", []) if item.get("type") == "file_search_call"]
    metrics = {"provider": "openai", "model": data.get("model"), "response_id": data.get("id"),
               "usage": data.get("usage"), "service_tier": data.get("service_tier"),
               "model_called": True, "file_search_calls": len(calls), "search_results": calls}
    try:
        if data.get("status") != "completed":
            raise LLMError("File Search generation did not complete; inspect output limits.")
        grouped = {}
        for call in calls:
            if call.get("status") != "completed":
                raise LLMError("File Search tool did not complete.")
            for hit in call.get("results") or []:
                file_id = hit.get("file_id")
                if file_id not in manifest["files"]:
                    raise LLMError("File Search returned a file outside the uploaded snapshot.")
                if isinstance(hit.get("text"), str) and hit["text"].strip():
                    grouped.setdefault(file_id, []).append(hit["text"])
        evidence = [Evidence(file_id, manifest["files"][file_id]["source"],
                             manifest["files"][file_id]["title"], None, None, "\n\n".join(texts))
                    for file_id, texts in grouped.items()]
        texts = []
        for item in data.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "refusal":
                        raise LLMError("OpenAI refused the request.")
                    if part.get("type") == "output_text":
                        texts.append(part["text"])
        status, statements, limitation, sources = parse_answer("".join(texts), evidence)
        # The model cites returned file IDs. Render compact labels only after validation.
        labels = {item.source_id: f"S{i}" for i, item in enumerate(evidence, 1)}
        from dataclasses import replace
        sources = [replace(item, source_id=labels[item.source_id]) for item in sources]
        evidence = [replace(item, source_id=labels[item.source_id]) for item in evidence]
        statements = [{**item, "source_ids": [labels[key] for key in item["source_ids"]]} for item in statements]
        metrics["source_labels"] = labels
        return status, statements, limitation, sources, evidence, metrics
    except (LLMError, KeyError, TypeError, ValueError) as exc:
        raise LLMError(f"Invalid File Search answer: {exc}", metrics=metrics) from None


class FileSearchAssistant:
    def __init__(self, config, documents, manifest_path, top_k=5):
        if config.provider != "openai" or not 1 <= top_k <= 50:
            raise ValueError("File Search requires --provider openai and --top-k between 1 and 50.")
        self.config, self.top_k = config, top_k
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.corpus_sha256 = corpus_fingerprint(documents)
        if (self.manifest.get("schema_version") != 1 or self.manifest.get("status") != "ready"
                or self.manifest.get("corpus_sha256") != self.corpus_sha256):
            raise ValueError("File Search snapshot is incomplete or stale. Upload the current corpus first.")
        self.client = sdk_client(config)
        store_id = self.manifest["vector_store_id"]
        store = remote(self.client.vector_stores.retrieve, vector_store_id=store_id)
        if store.status != "completed":
            raise ValueError("Remote vector store is expired or not ready.")
        # Validate the complete listing, including additional pages, before any generation.
        try:
            files = list(self.client.vector_stores.files.list(vector_store_id=store_id))
        except Exception:
            raise LLMError("Could not verify remote File Search snapshot.") from None
        if ({item.id for item in files} != set(self.manifest["files"])
                or any(item.status != "completed" for item in files)):
            raise ValueError("Remote file membership differs from the saved snapshot.")

    def ask(self, question):
        started = perf_counter()
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= self.config.max_question_chars:
            raise ValueError("Question is empty or exceeds the configured length limit.")
        prompt = SYSTEM_PROMPT.replace("evidence supplied in the user's JSON envelope",
                                       "evidence returned by the file_search tool")
        prompt += ("\nFor portfolio questions, search the supplied vector store before answering. "
                   "For unrelated requests, do not search; return the out-of-scope limitation. "
                   "Use the exact file_id values from search results in source_ids. "
                   "Do not use native citation markers in JSON text. Cite only retrieved files.")
        response = remote(self.client.responses.create, model=self.config.model,
                          instructions=prompt, input=question.strip(), store=False,
                          service_tier="default", truncation="disabled",
                          reasoning={"effort": self.config.reasoning_effort},
                          max_output_tokens=self.config.max_output_tokens,
                          tools=[{"type": "file_search", "vector_store_ids": [self.manifest["vector_store_id"]],
                                  "max_num_results": self.top_k}],
                          tool_choice="auto", include=["file_search_call.results"],
                          text={"format": {"type": "json_schema", "name": "portfolio_answer",
                                           "schema": ANSWER_SCHEMA, "strict": True}})
        status, statements, limitation, sources, evidence, metrics = decode_response(response.model_dump(), self.manifest)
        lines = [item["text"] + " " + " ".join(f"[{key}]" for key in item["source_ids"]) for item in statements]
        if limitation:
            lines.append(limitation)
        return Answer("file-search", status, "\n\n".join(lines), statements, limitation,
                      sources, evidence, perf_counter() - started, metrics)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["upload"])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--manifest", type=Path, default=Path("vector_db/file-search.json"))
    args = parser.parse_args(argv)
    try:
        upload(args.data_dir, args.manifest, LLMConfig(provider="openai", model="gpt-6-luna"))
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"Upload failed: {exc}\n")
    print("Upload complete. Existing files will be reused for questions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
